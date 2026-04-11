#define UNICODE
#define _UNICODE
#include <d3d11.h>
#include <dxgi1_2.h>
#include <d3dcompiler.h>
#include <windows.h>
#include <DirectXMath.h>
#include <wrl/client.h>
#include <vector>
#include <string>
#include <cstdio>
#include <cstdarg>

#pragma comment(lib, "d3d11.lib")
#pragma comment(lib, "dxgi.lib")
#pragma comment(lib, "d3dcompiler.lib")
#pragma comment(lib, "user32.lib")

using namespace Microsoft::WRL;
using namespace DirectX;

// ─── GPU Constant Buffer Layout (must match HLSL cbuffer Params) ────────────
//
// This struct is uploaded to the GPU every frame.  Engine-level config
// (VSync, quality, FPS cap) is intentionally kept out of here.

struct BlurlyGPUParams {
    XMFLOAT2 WindowPosition;   // 8 bytes
    XMFLOAT2 WindowSize;       // 8 bytes
    XMFLOAT2 ScreenResolution; // 8 bytes
    float RefractionStrength;  // 4 bytes
    float BlurStrength;        // 4 bytes
    int BlurType;              // 4 bytes  (0: Gaussian, 1: Frost)
    float FrostAmount;         // 4 bytes
    XMFLOAT2 Padding;          // 8 bytes  (total 48 = 16-byte aligned)
};

struct Vertex {
    XMFLOAT3 Pos;
    XMFLOAT2 UV;
};

// ─── Per-Instance State ─────────────────────────────────────────────────────

struct BlurlyInstance {
    // D3D11 core
    ComPtr<ID3D11Device>             device;
    ComPtr<ID3D11DeviceContext>      context;
    ComPtr<IDXGISwapChain1>          swapChain;
    ComPtr<IDXGIOutputDuplication>   deskDupl;
    ComPtr<ID3D11RenderTargetView>   renderTargetView;

    // Pipeline
    ComPtr<ID3D11VertexShader>       vertexShader;
    ComPtr<ID3D11InputLayout>        inputLayout;
    ComPtr<ID3D11Buffer>             vertexBuffer;
    ComPtr<ID3D11Buffer>             constantBuffer;
    ComPtr<ID3D11SamplerState>       samplerState;
    ComPtr<ID3D11ShaderResourceView> normalMapSRV;

    // 2-pass blur intermediate
    ComPtr<ID3D11Texture2D>          intermediateTexture;
    ComPtr<ID3D11RenderTargetView>   intermediateRTV;
    ComPtr<ID3D11ShaderResourceView> intermediateSRV;
    ComPtr<ID3D11PixelShader>        pixelShaderH;
    ComPtr<ID3D11PixelShader>        pixelShaderV;

    // Desktop capture caching
    ComPtr<ID3D11Texture2D>          lastDeskTex;
    ComPtr<ID3D11ShaderResourceView> lastDeskSRV;

    // GPU constant buffer data
    BlurlyGPUParams gpuParams;

    // ── Engine configuration (not uploaded to GPU) ──────────────────────────
    bool  vsync;        // VSync on Present (default: true)
    int   quality;      // 0 = performance (half-res intermediate), 1 = quality (full-res)
    float targetFPS;    // Max FPS cap; 0 = unlimited (default: 0)

    // Frame pacing state
    LARGE_INTEGER perfFreq;
    LARGE_INTEGER lastRenderTime;
    bool          hasRendered;

    // Intermediate RT dimensions (may differ from window size when quality=0)
    UINT intermediateW;
    UINT intermediateH;

    // Dirty rects buffer — reused across frames to avoid per-frame allocations
    std::vector<BYTE> dirtyRectsBuffer;

    HWND hwnd;
};

// ─── Thread-local error buffer ──────────────────────────────────────────────

static thread_local char g_ErrorBuffer[1024] = {0};

static void SetError(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vsnprintf(g_ErrorBuffer, sizeof(g_ErrorBuffer), fmt, args);
    va_end(args);
}

// ─── Internal helpers ───────────────────────────────────────────────────────

static bool CompileShaderFromFile(
    const wchar_t* path, const char* entry,
    const char* profile, ID3DBlob** blob)
{
    UINT flags = D3DCOMPILE_ENABLE_STRICTNESS;
    ComPtr<ID3DBlob> errorBlob;
    HRESULT hr = D3DCompileFromFile(
        path, nullptr, nullptr, entry, profile, flags, 0, blob, &errorBlob);
    if (FAILED(hr)) {
        if (errorBlob)
            SetError("Shader compile error: %s",
                     (char*)errorBlob->GetBufferPointer());
        else
            SetError("Failed to open shader file (HRESULT: 0x%08X)", hr);
        return false;
    }
    return true;
}

static bool LoadNormalMapFromFile(
    ID3D11Device* device, const char* path,
    ComPtr<ID3D11ShaderResourceView>& srv)
{
    FILE* f = fopen(path, "rb");
    if (!f) {
        SetError("Cannot open normal map: %s", path);
        return false;
    }

    std::vector<unsigned char> pixels(512 * 512 * 4);
    size_t bytesRead = fread(pixels.data(), 1, pixels.size(), f);
    fclose(f);

    if (bytesRead != pixels.size()) {
        SetError("Normal map too small: %s (got %zu, need %zu)",
                 path, bytesRead, pixels.size());
        return false;
    }

    D3D11_TEXTURE2D_DESC desc = {};
    desc.Width            = 512;
    desc.Height           = 512;
    desc.MipLevels        = 1;
    desc.ArraySize        = 1;
    desc.Format           = DXGI_FORMAT_R8G8B8A8_UNORM;
    desc.SampleDesc.Count = 1;
    desc.Usage            = D3D11_USAGE_DEFAULT;
    desc.BindFlags        = D3D11_BIND_SHADER_RESOURCE;

    D3D11_SUBRESOURCE_DATA subData = { pixels.data(), 512 * 4, 0 };
    ComPtr<ID3D11Texture2D> tex;
    HRESULT hr = device->CreateTexture2D(&desc, &subData, &tex);
    if (FAILED(hr)) {
        SetError("CreateTexture2D failed (0x%08X)", hr);
        return false;
    }

    srv.Reset();
    hr = device->CreateShaderResourceView(tex.Get(), nullptr, &srv);
    if (FAILED(hr)) {
        SetError("CreateSRV failed (0x%08X)", hr);
        return false;
    }
    return true;
}

static std::wstring ToWide(const std::string& s) {
    int len = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    std::wstring w(len, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, &w[0], len);
    return w;
}

// ─── Intermediate RT helper ────────────────────────────────────────────────
//
// Creates the blur intermediate at half or full resolution depending on the
// quality setting.  Half-res processes 4× fewer texels in pass 1 and the
// linear sampler handles free bilinear upscaling in pass 2.

static void RecreateIntermediate(BlurlyInstance* g, UINT windowW, UINT windowH) {
    UINT iw = (g->quality == 0) ? max(windowW / 2, 1u) : windowW;
    UINT ih = (g->quality == 0) ? max(windowH / 2, 1u) : windowH;

    g->intermediateTexture.Reset();
    g->intermediateRTV.Reset();
    g->intermediateSRV.Reset();

    D3D11_TEXTURE2D_DESC td = {};
    td.Width            = iw;
    td.Height           = ih;
    td.MipLevels        = 1;
    td.ArraySize        = 1;
    td.Format           = DXGI_FORMAT_B8G8R8A8_UNORM;
    td.SampleDesc.Count = 1;
    td.Usage            = D3D11_USAGE_DEFAULT;
    td.BindFlags        = D3D11_BIND_RENDER_TARGET | D3D11_BIND_SHADER_RESOURCE;

    g->device->CreateTexture2D(&td, nullptr, &g->intermediateTexture);
    g->device->CreateRenderTargetView(g->intermediateTexture.Get(), nullptr, &g->intermediateRTV);
    g->device->CreateShaderResourceView(g->intermediateTexture.Get(), nullptr, &g->intermediateSRV);

    g->intermediateW = iw;
    g->intermediateH = ih;
}

// ─── Exported API ───────────────────────────────────────────────────────────

extern "C" {

__declspec(dllexport) void*       Blurly_Create(HWND hwnd, const char* shaderDir, const char* normalMapPath);
__declspec(dllexport) void        Blurly_Destroy(void* instance);
__declspec(dllexport) void        Blurly_UpdatePosition(void* instance, int x, int y, int w, int h);
__declspec(dllexport) void        Blurly_SetParams(void* instance, float refraction, float blur, int type, float frost);
__declspec(dllexport) void        Blurly_SetConfig(void* instance, int vsync, int quality, float targetFPS);
__declspec(dllexport) bool        Blurly_LoadNormalMap(void* instance, const char* path);
__declspec(dllexport) void        Blurly_Render(void* instance);
__declspec(dllexport) void        Blurly_RenderAt(void* instance, int x, int y, int w, int h);
__declspec(dllexport) const char* Blurly_GetError();

} // extern "C"

// ─── Blurly_Create ──────────────────────────────────────────────────────────────

void* Blurly_Create(HWND hwnd, const char* shaderDir, const char* normalMapPath) {
    auto* inst = new BlurlyInstance();
    inst->hwnd      = hwnd;
    inst->gpuParams = { {0,0}, {800,600}, {1920,1080}, 0.05f, 3.0f, 0, 0.5f, {0,0} };

    // Engine config defaults
    inst->vsync       = true;
    inst->quality     = 1;       // Full quality by default
    inst->targetFPS   = 0.0f;    // Unlimited
    inst->hasRendered = false;

    // Frame pacing init
    QueryPerformanceFrequency(&inst->perfFreq);
    inst->lastRenderTime.QuadPart = 0;

    // Pre-allocate dirty rects buffer (enough for ~64 rects initially)
    inst->dirtyRectsBuffer.resize(64 * sizeof(RECT));

    // Exclude from Desktop Duplication capture (prevents hall-of-mirrors)
    SetWindowDisplayAffinity(hwnd, 0x00000011 /* WDA_EXCLUDEFROMCAPTURE */);

    // ── D3D11 Device ────────────────────────────────────────────────────────
    D3D_FEATURE_LEVEL levels[] = { D3D_FEATURE_LEVEL_11_0 };
    HRESULT hr = D3D11CreateDevice(
        nullptr, D3D_DRIVER_TYPE_HARDWARE, nullptr, 0,
        levels, 1, D3D11_SDK_VERSION,
        &inst->device, nullptr, &inst->context);
    if (FAILED(hr)) {
        SetError("D3D11CreateDevice failed (0x%08X)", hr);
        delete inst; return nullptr;
    }

    // ── Swap Chain ──────────────────────────────────────────────────────────
    ComPtr<IDXGIDevice>  dxgiDev;   inst->device.As(&dxgiDev);
    ComPtr<IDXGIAdapter> adapter;   dxgiDev->GetAdapter(&adapter);
    ComPtr<IDXGIFactory2> factory;  adapter->GetParent(IID_PPV_ARGS(&factory));

    RECT rc; GetClientRect(hwnd, &rc);
    DXGI_SWAP_CHAIN_DESC1 sc = {};
    sc.Width       = rc.right  - rc.left;
    sc.Height      = rc.bottom - rc.top;
    sc.Format      = DXGI_FORMAT_B8G8R8A8_UNORM;
    sc.SampleDesc  = { 1, 0 };
    sc.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    sc.BufferCount = 2;
    sc.SwapEffect  = DXGI_SWAP_EFFECT_FLIP_DISCARD;
    sc.AlphaMode   = DXGI_ALPHA_MODE_UNSPECIFIED;

    hr = factory->CreateSwapChainForHwnd(
        inst->device.Get(), hwnd, &sc, nullptr, nullptr, &inst->swapChain);
    if (FAILED(hr)) {
        SetError("CreateSwapChainForHwnd failed (0x%08X)", hr);
        delete inst; return nullptr;
    }

    ComPtr<ID3D11Texture2D> bb;
    inst->swapChain->GetBuffer(0, IID_PPV_ARGS(&bb));
    inst->device->CreateRenderTargetView(bb.Get(), nullptr, &inst->renderTargetView);

    // ── Desktop Duplication ─────────────────────────────────────────────────
    ComPtr<IDXGIOutput> output;
    hr = adapter->EnumOutputs(0, &output);
    if (FAILED(hr)) {
        SetError("EnumOutputs failed (0x%08X)", hr);
        delete inst; return nullptr;
    }

    ComPtr<IDXGIOutput1> output1;
    output.As(&output1);
    hr = output1->DuplicateOutput(inst->device.Get(), &inst->deskDupl);
    if (FAILED(hr)) {
        SetError("DuplicateOutput failed (0x%08X)", hr);
        delete inst; return nullptr;
    }

    DXGI_OUTPUT_DESC od;
    output->GetDesc(&od);
    inst->gpuParams.ScreenResolution.x = (float)(od.DesktopCoordinates.right  - od.DesktopCoordinates.left);
    inst->gpuParams.ScreenResolution.y = (float)(od.DesktopCoordinates.bottom - od.DesktopCoordinates.top);

    // ── Shaders ─────────────────────────────────────────────────────────────
    std::string dir(shaderDir);
    if (!dir.empty() && dir.back() != '\\' && dir.back() != '/')
        dir += '\\';

    std::wstring hPath = ToWide(dir + "BlurlyH.hlsl");
    std::wstring vPath = ToWide(dir + "BlurlyV.hlsl");

    // Inline vertex shader (trivial pass-through)
    const char* vsSrc =
        "struct VS_IN { float3 Pos : POSITION; float2 UV : TEXCOORD; };"
        "struct PS_IN { float4 Pos : SV_POSITION; float2 UV : TEXCOORD; };"
        "PS_IN main(VS_IN i) {"
        "  PS_IN o; o.Pos = float4(i.Pos, 1.0); o.UV = i.UV; return o;"
        "}";

    ComPtr<ID3DBlob> vsBlob;
    D3DCompile(vsSrc, strlen(vsSrc), nullptr, nullptr, nullptr,
               "main", "vs_4_0", 0, 0, &vsBlob, nullptr);
    inst->device->CreateVertexShader(
        vsBlob->GetBufferPointer(), vsBlob->GetBufferSize(),
        nullptr, &inst->vertexShader);

    ComPtr<ID3DBlob> psBlob;
    if (!CompileShaderFromFile(hPath.c_str(), "main", "ps_4_0", &psBlob)) {
        delete inst; return nullptr;
    }
    inst->device->CreatePixelShader(
        psBlob->GetBufferPointer(), psBlob->GetBufferSize(),
        nullptr, &inst->pixelShaderH);

    if (!CompileShaderFromFile(vPath.c_str(), "main", "ps_4_0", &psBlob)) {
        delete inst; return nullptr;
    }
    inst->device->CreatePixelShader(
        psBlob->GetBufferPointer(), psBlob->GetBufferSize(),
        nullptr, &inst->pixelShaderV);

    // ── Intermediate RT (for 2-pass blur) ───────────────────────────────────
    inst->gpuParams.WindowSize = { (float)sc.Width, (float)sc.Height };
    RecreateIntermediate(inst, sc.Width, sc.Height);

    // ── Input Layout ────────────────────────────────────────────────────────
    D3D11_INPUT_ELEMENT_DESC ild[] = {
        { "POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0,  0, D3D11_INPUT_PER_VERTEX_DATA, 0 },
        { "TEXCOORD", 0, DXGI_FORMAT_R32G32_FLOAT,    0, 12, D3D11_INPUT_PER_VERTEX_DATA, 0 },
    };
    inst->device->CreateInputLayout(
        ild, 2, vsBlob->GetBufferPointer(), vsBlob->GetBufferSize(),
        &inst->inputLayout);

    // ── Fullscreen Quad ─────────────────────────────────────────────────────
    Vertex verts[] = {
        { {-1, 1, 0}, {0, 0} },  { {1, 1, 0}, {1, 0} },  { {-1,-1, 0}, {0, 1} },
        { {-1,-1, 0}, {0, 1} },  { {1, 1, 0}, {1, 0} },  { { 1,-1, 0}, {1, 1} },
    };
    D3D11_BUFFER_DESC vbd = { sizeof(verts), D3D11_USAGE_DEFAULT, D3D11_BIND_VERTEX_BUFFER, 0, 0, 0 };
    D3D11_SUBRESOURCE_DATA vd = { verts, 0, 0 };
    inst->device->CreateBuffer(&vbd, &vd, &inst->vertexBuffer);

    // ── Constant Buffer ─────────────────────────────────────────────────────
    D3D11_BUFFER_DESC cbd = { sizeof(BlurlyGPUParams), D3D11_USAGE_DYNAMIC,
                              D3D11_BIND_CONSTANT_BUFFER, D3D11_CPU_ACCESS_WRITE, 0, 0 };
    inst->device->CreateBuffer(&cbd, nullptr, &inst->constantBuffer);

    // ── Sampler ─────────────────────────────────────────────────────────────
    D3D11_SAMPLER_DESC sd = {};
    sd.Filter         = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU       = D3D11_TEXTURE_ADDRESS_CLAMP;
    sd.AddressV       = D3D11_TEXTURE_ADDRESS_CLAMP;
    sd.AddressW       = D3D11_TEXTURE_ADDRESS_CLAMP;
    sd.ComparisonFunc = D3D11_COMPARISON_NEVER;
    sd.MinLOD         = 0;
    sd.MaxLOD         = D3D11_FLOAT32_MAX;
    inst->device->CreateSamplerState(&sd, &inst->samplerState);

    // ── Normal Map ──────────────────────────────────────────────────────────
    if (normalMapPath && normalMapPath[0]) {
        if (!LoadNormalMapFromFile(inst->device.Get(), normalMapPath, inst->normalMapSRV)) {
            delete inst; return nullptr;
        }
    }

    return inst;
}

// ─── Blurly_Destroy ─────────────────────────────────────────────────────────────

void Blurly_Destroy(void* handle) {
    if (handle) delete static_cast<BlurlyInstance*>(handle);
}

// ─── Blurly_UpdatePosition ─────────────────────────────────────────────────────

void Blurly_UpdatePosition(void* handle, int x, int y, int w, int h) {
    if (!handle) return;
    auto* g = static_cast<BlurlyInstance*>(handle);

    bool resized = (w != (int)g->gpuParams.WindowSize.x ||
                    h != (int)g->gpuParams.WindowSize.y);
    g->gpuParams.WindowPosition = { (float)x, (float)y };
    g->gpuParams.WindowSize     = { (float)w, (float)h };

    if (resized && g->device && w > 0 && h > 0) {
        // Recreate intermediate RT at appropriate resolution for quality level
        RecreateIntermediate(g, (UINT)w, (UINT)h);

        // Resize swap chain
        g->renderTargetView.Reset();
        g->swapChain->ResizeBuffers(2, (UINT)w, (UINT)h, DXGI_FORMAT_B8G8R8A8_UNORM, 0);
        ComPtr<ID3D11Texture2D> bb;
        g->swapChain->GetBuffer(0, IID_PPV_ARGS(&bb));
        g->device->CreateRenderTargetView(bb.Get(), nullptr, &g->renderTargetView);
    }
}

// ─── Blurly_SetParams ───────────────────────────────────────────────────────────

void Blurly_SetParams(void* handle, float refraction, float blur, int type, float frost) {
    if (!handle) return;
    auto* g = static_cast<BlurlyInstance*>(handle);
    g->gpuParams.RefractionStrength = refraction;
    g->gpuParams.BlurStrength       = blur;
    g->gpuParams.BlurType           = type;
    g->gpuParams.FrostAmount        = frost;
}

// ─── Blurly_SetConfig ───────────────────────────────────────────────────────────
//
// Engine-level configuration that doesn't affect the GPU constant buffer:
//   vsync     – 1 = VSync on, 0 = off
//   quality   – 0 = performance (half-res blur), 1 = quality (full-res blur)
//   targetFPS – max frame rate cap (0 = unlimited)

void Blurly_SetConfig(void* handle, int vsync, int quality, float targetFPS) {
    if (!handle) return;
    auto* g = static_cast<BlurlyInstance*>(handle);

    g->vsync     = (vsync != 0);
    g->targetFPS = targetFPS;

    // If quality changed, recreate intermediate RT at the new resolution
    if (quality != g->quality) {
        g->quality = quality;
        UINT w = (UINT)g->gpuParams.WindowSize.x;
        UINT h = (UINT)g->gpuParams.WindowSize.y;
        if (g->device && w > 0 && h > 0) {
            RecreateIntermediate(g, w, h);
        }
    }
}

// ─── Blurly_LoadNormalMap ───────────────────────────────────────────────────────

bool Blurly_LoadNormalMap(void* handle, const char* path) {
    if (!handle) return false;
    auto* g = static_cast<BlurlyInstance*>(handle);
    return LoadNormalMapFromFile(g->device.Get(), path, g->normalMapSRV);
}

// ─── Blurly_Render ──────────────────────────────────────────────────────────────

void Blurly_Render(void* handle) {
    if (!handle) return;
    auto* g = static_cast<BlurlyInstance*>(handle);
    if (!g->deskDupl) return;

    // ── Frame pacing: skip if called faster than target FPS ─────────────────
    if (g->targetFPS > 0.0f) {
        LARGE_INTEGER now;
        QueryPerformanceCounter(&now);
        if (g->hasRendered) {
            double elapsed = (double)(now.QuadPart - g->lastRenderTime.QuadPart)
                           / (double)g->perfFreq.QuadPart;
            if (elapsed < (1.0 / (double)g->targetFPS))
                return;  // Too soon — skip this frame
        }
    }

    auto* ctx = g->context.Get();
    ComPtr<IDXGIResource> deskRes;
    DXGI_OUTDUPL_FRAME_INFO fi;
    HRESULT hr = g->deskDupl->AcquireNextFrame(0, &fi, &deskRes);

    if (SUCCEEDED(hr)) {
        ComPtr<ID3D11Texture2D> deskTex;
        deskRes.As(&deskTex);
        
        D3D11_TEXTURE2D_DESC desc;
        deskTex->GetDesc(&desc);
        
        bool needsNewTexture = true;
        if (g->lastDeskTex) {
            D3D11_TEXTURE2D_DESC cachedDesc;
            g->lastDeskTex->GetDesc(&cachedDesc);
            if (cachedDesc.Width == desc.Width && cachedDesc.Height == desc.Height && cachedDesc.Format == desc.Format) {
                needsNewTexture = false;
            }
        }
        
        if (needsNewTexture) {
            // First frame or desktop format changed — create texture and full copy
            g->lastDeskTex.Reset();
            g->lastDeskSRV.Reset();
            desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;
            desc.MiscFlags = 0;
            desc.Usage = D3D11_USAGE_DEFAULT;
            g->device->CreateTexture2D(&desc, nullptr, &g->lastDeskTex);
            g->device->CreateShaderResourceView(g->lastDeskTex.Get(), nullptr, &g->lastDeskSRV);
            ctx->CopyResource(g->lastDeskTex.Get(), deskTex.Get());
        } else {
            // ── Dirty-region copy: only update changed areas ────────────────
            //
            // Check for move rects first.  If any exist, fall back to a full
            // CopyResource because handling overlapping self-copies from move
            // rects adds significant complexity for marginal gain.
            DXGI_OUTDUPL_MOVE_RECT moveBuf;
            UINT moveSize = sizeof(moveBuf);
            HRESULT moveHr = g->deskDupl->GetFrameMoveRects(
                sizeof(moveBuf), &moveBuf, &moveSize);
            bool hasMoves = (moveHr == DXGI_ERROR_MORE_DATA ||
                             (SUCCEEDED(moveHr) && moveSize > 0));

            if (hasMoves) {
                ctx->CopyResource(g->lastDeskTex.Get(), deskTex.Get());
            } else {
                // No moves — try partial copy via dirty rects
                UINT dirtySize = (UINT)g->dirtyRectsBuffer.size();
                HRESULT drhr = g->deskDupl->GetFrameDirtyRects(
                    dirtySize,
                    reinterpret_cast<RECT*>(g->dirtyRectsBuffer.data()),
                    &dirtySize);

                if (drhr == DXGI_ERROR_MORE_DATA) {
                    // Buffer too small — resize and retry
                    g->dirtyRectsBuffer.resize(dirtySize);
                    drhr = g->deskDupl->GetFrameDirtyRects(
                        dirtySize,
                        reinterpret_cast<RECT*>(g->dirtyRectsBuffer.data()),
                        &dirtySize);
                }

                if (SUCCEEDED(drhr) && dirtySize > 0) {
                    UINT numRects = dirtySize / sizeof(RECT);
                    auto* rects = reinterpret_cast<RECT*>(g->dirtyRectsBuffer.data());
                    for (UINT i = 0; i < numRects; i++) {
                        D3D11_BOX box;
                        box.left   = (UINT)rects[i].left;
                        box.top    = (UINT)rects[i].top;
                        box.front  = 0;
                        box.right  = (UINT)rects[i].right;
                        box.bottom = (UINT)rects[i].bottom;
                        box.back   = 1;
                        ctx->CopySubresourceRegion(
                            g->lastDeskTex.Get(), 0,
                            rects[i].left, rects[i].top, 0,
                            deskTex.Get(), 0, &box);
                    }
                } else if (FAILED(drhr)) {
                    // GetFrameDirtyRects failed — fall back to full copy
                    ctx->CopyResource(g->lastDeskTex.Get(), deskTex.Get());
                }
                // else: SUCCEEDED with dirtySize == 0 → no pixel changes, skip copy
            }
        }
        
        g->deskDupl->ReleaseFrame();
    } else if (hr == DXGI_ERROR_WAIT_TIMEOUT) {
        if (!g->lastDeskSRV) return;
    } else {
        return;
    }

    // ── Shared pipeline state ───────────────────────────────────────────────
    ctx->IASetInputLayout(g->inputLayout.Get());
    ctx->IASetPrimitiveTopology(D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ID3D11Buffer* vbs[] = { g->vertexBuffer.Get() };
    UINT strides[] = { sizeof(Vertex) };
    UINT offsets[] = { 0 };
    ctx->IASetVertexBuffers(0, 1, vbs, strides, offsets);
    ctx->VSSetShader(g->vertexShader.Get(), nullptr, 0);
    ctx->PSSetConstantBuffers(0, 1, g->constantBuffer.GetAddressOf());
    ctx->PSSetSamplers(0, 1, g->samplerState.GetAddressOf());

    // Update constant buffer
    D3D11_MAPPED_SUBRESOURCE mapped;
    if (SUCCEEDED(ctx->Map(g->constantBuffer.Get(), 0, D3D11_MAP_WRITE_DISCARD, 0, &mapped))) {
        memcpy(mapped.pData, &g->gpuParams, sizeof(BlurlyGPUParams));
        ctx->Unmap(g->constantBuffer.Get(), 0);
    }

    // ── Pass 1 — Horizontal blur at intermediate resolution ─────────────────
    D3D11_VIEWPORT intermediateVP = { 0, 0, (float)g->intermediateW, (float)g->intermediateH, 0, 1 };
    ctx->RSSetViewports(1, &intermediateVP);
    ctx->OMSetRenderTargets(1, g->intermediateRTV.GetAddressOf(), nullptr);
    ctx->PSSetShader(g->pixelShaderH.Get(), nullptr, 0);
    ID3D11ShaderResourceView* srv1[] = { g->lastDeskSRV.Get(), g->normalMapSRV.Get() };
    ctx->PSSetShaderResources(0, 2, srv1);
    ctx->Draw(6, 0);

    // ── Pass 2 — Vertical blur + upsample to full resolution ────────────────
    D3D11_VIEWPORT fullVP = { 0, 0, g->gpuParams.WindowSize.x, g->gpuParams.WindowSize.y, 0, 1 };
    ctx->RSSetViewports(1, &fullVP);
    ctx->OMSetRenderTargets(1, g->renderTargetView.GetAddressOf(), nullptr);
    ctx->PSSetShader(g->pixelShaderV.Get(), nullptr, 0);
    ID3D11ShaderResourceView* srv2[] = { g->intermediateSRV.Get(), g->normalMapSRV.Get() };
    ctx->PSSetShaderResources(0, 2, srv2);
    ctx->Draw(6, 0);

    // Unbind SRVs to avoid D3D11 hazard warnings
    ID3D11ShaderResourceView* nul[] = { nullptr, nullptr };
    ctx->PSSetShaderResources(0, 2, nul);

    // Present with configurable VSync
    g->swapChain->Present(g->vsync ? 1 : 0, 0);

    // Update frame pacing timestamp
    QueryPerformanceCounter(&g->lastRenderTime);
    g->hasRendered = true;
}

// ─── Blurly_RenderAt (combined position update + render in one C call) ──────

void Blurly_RenderAt(void* handle, int x, int y, int w, int h) {
    Blurly_UpdatePosition(handle, x, y, w, h);
    Blurly_Render(handle);
}

// ─── Blurly_GetError ────────────────────────────────────────────────────────────

const char* Blurly_GetError() { return g_ErrorBuffer; }

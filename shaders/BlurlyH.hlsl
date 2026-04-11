Texture2D DesktopTexture : register(t0);
Texture2D NormalMap : register(t1);
SamplerState samLinear : register(s0);

cbuffer Params : register(b0) {
    float2 WindowPosition;
    float2 WindowSize;
    float2 ScreenResolution;
    float RefractionStrength;
    float BlurStrength;
    int BlurType;
    float FrostAmount;
    float Transparency;
    float EdgeHighlight;
    float3 TintColor;
};

struct PS_IN {
    float4 Pos : SV_POSITION;
    float2 UV : TEXCOORD;
};

// Pseudo-random noise for Frost
float rand(float2 co) {
    return frac(sin(dot(co.xy, float2(12.9898, 78.233))) * 43758.5453);
}

float4 main(PS_IN input) : SV_Target {
    // 1. Calculate Desktop UV
    float2 screenPixel = input.UV * WindowSize + WindowPosition;
    float2 desktopUV = screenPixel / ScreenResolution;

    // 2. Sample Normal Map for Refraction
    float4 normalData = NormalMap.Sample(samLinear, input.UV * 2.0); // Tiled
    float2 distortion = (normalData.rg * 2.0 - 1.0) * RefractionStrength;
    
    float2 baseUV = desktopUV + distortion;

    // 3. Horizontal Blur — 5-tap linear Gaussian (≈ 9-tap)
    //    Pre-normalized weights sum to 1.0 — no division needed.
    //    Fully unrolled for zero branch overhead.
    float blurRadius = BlurStrength / ScreenResolution.x;

    // Center tap (weight 0.227027)
    float4 color = DesktopTexture.Sample(samLinear, baseUV) * 0.227027;

    // Tap 1 — offset 1.384615 (weight 0.316216 per side)
    float off1 = 1.384615 * blurRadius;
    float j1 = (BlurType == 1) ? (rand(input.UV + 1.0) * FrostAmount * blurRadius) : 0;
    color += DesktopTexture.Sample(samLinear, baseUV + float2(off1 + j1, 0)) * 0.316216;
    color += DesktopTexture.Sample(samLinear, baseUV - float2(off1 + j1, 0)) * 0.316216;

    // Tap 2 — offset 3.230769 (weight 0.070270 per side)
    float off2 = 3.230769 * blurRadius;
    float j2 = (BlurType == 1) ? (rand(input.UV + 2.0) * FrostAmount * blurRadius) : 0;
    color += DesktopTexture.Sample(samLinear, baseUV + float2(off2 + j2, 0)) * 0.070270;
    color += DesktopTexture.Sample(samLinear, baseUV - float2(off2 + j2, 0)) * 0.070270;

    return color;
}

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
    float2 Padding;
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

    // 3. Multi-Pass Horizontal Blur
    float4 color = 0;
    float totalWeight = 0;
    float blurRadius = BlurStrength / ScreenResolution.x;
    
    // 5-tap linear interpolated Gaussian (equivalent to 9-tap)
    float weights[3] = { 0.227027, 0.316216, 0.070270 };
    float offsets[3] = { 0.0, 1.384615, 3.230769 };
    
    color += DesktopTexture.Sample(samLinear, baseUV) * weights[0];
    totalWeight += weights[0];
    
    for(int i = 1; i < 3; i++) {
        float offset = offsets[i] * blurRadius;
        
        // Dynamic Frost jitter
        float jitter = (BlurType == 1) ? (rand(input.UV + float(i)) * FrostAmount * blurRadius) : 0;
        
        color += DesktopTexture.Sample(samLinear, baseUV + float2(offset + jitter, 0)) * weights[i];
        color += DesktopTexture.Sample(samLinear, baseUV - float2(offset + jitter, 0)) * weights[i];
        totalWeight += weights[i] * 2.0;
    }

    return color / totalWeight;
}

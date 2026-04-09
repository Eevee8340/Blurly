Texture2D IntermediateTexture : register(t0);
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
    float2 baseUV = input.UV;

    // 1. Multi-Pass Vertical Blur
    float4 color = 0;
    float totalWeight = 0;
    float blurRadius = BlurStrength / ScreenResolution.y;
    
    // Standard 9-tap Gaussian approximation
    float weights[5] = { 0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216 };
    
    color += IntermediateTexture.Sample(samLinear, baseUV) * weights[0];
    totalWeight += weights[0];
    
    for(int i = 1; i < 5; i++) {
        float offset = float(i) * blurRadius;
        
        // Dynamic Frost jitter
        float jitter = (BlurType == 1) ? (rand(input.UV + float(i)*1.5) * FrostAmount * blurRadius) : 0;
        
        color += IntermediateTexture.Sample(samLinear, baseUV + float2(0, offset + jitter)) * weights[i];
        color += IntermediateTexture.Sample(samLinear, baseUV - float2(0, offset + jitter)) * weights[i];
        totalWeight += weights[i] * 2.0;
    }

    float4 final = color / totalWeight;
    
    // Add subtle grain overlay if Frost is enabled
    if (BlurType == 1) {
        float noise = rand(input.UV);
        final.rgb += (noise - 0.5) * FrostAmount * 0.1;
    }
    
    // Force Alpha to 1.0 (some windows need this to be opaque but blurred)
    final.a = 1.0;
    return final;
}

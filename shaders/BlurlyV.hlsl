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
    float Transparency;
    float EdgeHighlight;
    float3 TintColor;
};

struct PS_IN {
    float4 Pos : SV_POSITION;
    float2 UV : TEXCOORD;
};

Texture2D NoiseMap : register(t2);
SamplerState samWrap : register(s1);

// Pseudo-random noise for Frost
float rand(float2 co) {
    return NoiseMap.Sample(samWrap, co * ScreenResolution / 512.0).r;
}

float4 main(PS_IN input) : SV_Target {
    float2 baseUV = input.UV;

    // 1. Vertical Blur — 5-tap linear Gaussian (≈ 9-tap)
    //    Pre-normalized weights sum to 1.0 — no division needed.
    //    Fully unrolled for zero branch overhead.
    float blurRadius = BlurStrength / ScreenResolution.y;

    // Center tap (weight 0.227027)
    float4 color = IntermediateTexture.Sample(samLinear, baseUV) * 0.227027;

    // Tap 1 — offset 1.384615 (weight 0.316216 per side)
    float off1 = 1.384615 * blurRadius;
    float j1 = (BlurType == 1) ? (rand(input.UV + 1.5) * FrostAmount * blurRadius) : 0;
    color += IntermediateTexture.Sample(samLinear, baseUV + float2(0, off1 + j1)) * 0.316216;
    color += IntermediateTexture.Sample(samLinear, baseUV - float2(0, off1 + j1)) * 0.316216;

    // Tap 2 — offset 3.230769 (weight 0.070270 per side)
    float off2 = 3.230769 * blurRadius;
    float j2 = (BlurType == 1) ? (rand(input.UV + 3.0) * FrostAmount * blurRadius) : 0;
    color += IntermediateTexture.Sample(samLinear, baseUV + float2(0, off2 + j2)) * 0.070270;
    color += IntermediateTexture.Sample(samLinear, baseUV - float2(0, off2 + j2)) * 0.070270;

    float4 final_color = color;

    // Add subtle grain overlay if Frost is enabled
    if (BlurType == 1) {
        float noise = rand(input.UV);
        final_color.rgb += (noise - 0.5) * FrostAmount * 0.1;
    }
    
    // Apply Tint
    final_color.rgb = lerp(final_color.rgb, TintColor, Transparency);

    // Apply Edge Highlight (subtle inner glow at the edges of the window)
    float2 dist = abs(input.UV - 0.5) * 2.0; // 0.0 at center, 1.0 at edges
    float edgeMask = max(dist.x, dist.y);
    edgeMask = pow(edgeMask, 4.0); // push it closer to the edges
    final_color.rgb += edgeMask * EdgeHighlight;

    // Force Alpha to 1.0 (some windows need this to be opaque but blurred)
    final_color.a = 1.0;
    return final_color;
}

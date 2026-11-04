#version 330 core

in vec2 v_texCoord;

uniform sampler2D u_diffuseTexture;
uniform bool u_useAlphaTest;
uniform float u_alphaThreshold;

void main()
{
    // Keep transparent gaps in foliage from becoming solid shadow casters.
    if (u_useAlphaTest)
    {
        float alpha = texture(u_diffuseTexture, v_texCoord).a;
        if (alpha < u_alphaThreshold)
            discard;
    }

    // The rasterizer writes gl_FragCoord.z to the bound depth attachment.
}

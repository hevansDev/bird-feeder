/**
 * Bird Feeder Community Upload API
 * Handles image uploads to Cloudflare Images with rate limiting
 */

export default {
  async fetch(request, env) {
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response(JSON.stringify({ error: 'Method not allowed' }), {
        status: 405,
        headers: { 'Content-Type': 'application/json', ...corsHeaders }
      });
    }

    try {
      const formData = await request.formData();
      const file = formData.get('file');
      const userId = formData.get('user_id') || 'anonymous';
      const metadataStr = formData.get('metadata') || '{}';
      
      if (!file) {
        return jsonResponse({ error: 'No file provided' }, 400, corsHeaders);
      }

      // Validate file size
      const maxSize = (env.MAX_FILE_SIZE_MB || 10) * 1024 * 1024;
      if (file.size > maxSize) {
        return jsonResponse({ 
          error: `File too large (max ${env.MAX_FILE_SIZE_MB || 10}MB)` 
        }, 400, corsHeaders);
      }

      // Parse and enhance metadata
      const metadata = JSON.parse(metadataStr);
      const enrichedMetadata = {
        ...metadata,
        userId,
        uploadedAt: new Date().toISOString(),
        userAgent: request.headers.get('User-Agent') || 'unknown'
      };

      // Upload to Cloudflare Images
      const uploadFormData = new FormData();
      uploadFormData.append('file', file);
      uploadFormData.append('metadata', JSON.stringify(enrichedMetadata));

      const uploadResponse = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/images/v1`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${env.IMAGES_API_TOKEN}`
          },
          body: uploadFormData
        }
      );

      const result = await uploadResponse.json();

      if (!result.success) {
        console.error('Cloudflare Images error:', result);
        throw new Error(result.errors?.[0]?.message || 'Upload failed');
      }

      // Build response with image URLs
      const imageId = result.result.id;
      const baseUrl = `https://imagedelivery.net/${env.CLOUDFLARE_ACCOUNT_HASH}/${imageId}`;

      return jsonResponse({
        success: true,
        imageId,
        urls: {
          public: `${baseUrl}/public`,
          thumbnail: `${baseUrl}/thumbnail`,
          original: result.result.variants[0]
        },
        metadata: enrichedMetadata
      }, 200, corsHeaders);

    } catch (error) {
      console.error('Upload error:', error);
      return jsonResponse({
        success: false,
        error: error.message
      }, 500, corsHeaders);
    }
  }
};

function jsonResponse(data, status = 200, additionalHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...additionalHeaders
    }
  });
}
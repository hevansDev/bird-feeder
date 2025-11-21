/**
 * Bird Feeder Community Upload API
 * Handles image uploads to Cloudflare Images with rate limiting
 * Also serves a public gallery at /gallery
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Gallery page
    if (url.pathname === '/gallery' && request.method === 'GET') {
      return serveGallery(env);
    }
    
    // CORS headers
    const corsHeaders = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle CORS preflight
    if (request.method === 'OPTIONS') {
      return new Response(null, { headers: corsHeaders });
    }

    if (request.method !== 'POST') {
      return new Response('Method not allowed', { status: 405 });
    }

    // Upload handler
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

async function serveGallery(env) {
  try {
    // Fetch images using server-side API token (secure!)
    const response = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/images/v2?per_page=100`,
      {
        headers: { 'Authorization': `Bearer ${env.IMAGES_API_TOKEN}` }
      }
    );
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error('Failed to fetch images');
    }
    
    const images = data.result.images || [];
    
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Bird Feeder Gallery</title>
        <link rel="icon" type="image/x-icon" href="https://hughevans.dev/favicon.ico">
        <script defer src="https://umami.hughevans.dev/script.js" data-website-id="518b3fb7-378f-4bb7-99aa-659f7825b457"></script>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
          * { margin: 0; padding: 0; box-sizing: border-box; }
          body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
          }
          h1 { 
            text-align: center;
            margin-bottom: 30px;
            color: #333;
          }
          .stats {
            text-align: center;
            margin-bottom: 30px;
            color: #666;
          }
          .grid { 
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
          }
          .card { 
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
          }
          .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.15);
          }
          .card img { 
            width: 100%;
            height: 300px;
            object-fit: cover;
            cursor: pointer;
            display: block;
          }
          .info { 
            padding: 15px;
          }
          .weight { 
            font-weight: bold;
            color: #2563eb;
            font-size: 18px;
            margin-bottom: 8px;
          }
          .meta { 
            color: #666;
            font-size: 14px;
            margin-top: 4px;
          }
          .user { 
            color: #16a34a;
            font-weight: 500;
          }
          @media (max-width: 768px) {
            .grid {
              grid-template-columns: 1fr;
            }
          }
        </style>
      </head>
      <body>
        <h1>Bird Feeder Community Gallery</h1>
        <div class="stats">
          Total photos: ${images.length}
        </div>
        <div class="grid">
          ${images.map(img => {
            const meta = img.meta || {};
            const date = new Date(img.uploaded);
            return `
              <div class="card">
                <img 
                  src="${img.variants[0]}" 
                  alt="Bird photo"
                  onclick="window.open('${img.variants[0]}', '_blank')"
                  loading="lazy"
                >
                <div class="info">
                  <div class="weight">Weight: ${meta.weight ? meta.weight + 'g' : 'N/A'}</div>
                  <div class="meta user"> ${meta.userId || 'Anonymous'}</div>
                  <div class="meta"> ${meta.location || 'Unknown location'}</div>
                  <div class="meta"> ${meta.detectionType || 'Unknown'}</div>
                  <div class="meta"> ${date.toLocaleDateString()} ${date.toLocaleTimeString()}</div>
                </div>
              </div>
            `;
          }).join('')}
        </div>
      </body>
      </html>
    `;
    
    return new Response(html, {
      headers: { 
        'Content-Type': 'text/html',
        'Cache-Control': 'public, max-age=300'
      }
    });
    
  } catch (error) {
    return new Response(`Error loading gallery: ${error.message}`, {
      status: 500,
      headers: { 'Content-Type': 'text/plain' }
    });
  }
}
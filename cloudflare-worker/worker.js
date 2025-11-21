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
    
    // API endpoint for loading more images
    if (url.pathname === '/api/images' && request.method === 'GET') {
      return fetchImagesAPI(request, env);
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

async function fetchImagesAPI(request, env) {
  try {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1');
    const perPage = 50;
    
    const response = await fetch(
      `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/images/v1?per_page=${perPage}&page=${page}`,
      {
        headers: { 'Authorization': `Bearer ${env.IMAGES_API_TOKEN}` }
      }
    );
    
    const data = await response.json();
    
    if (!data.success) {
      throw new Error('Failed to fetch images');
    }
    
    // Get total count on first page only
    let total = 0;
    if (page === 1) {
      // Make a separate request to get just the count
      const countResponse = await fetch(
        `https://api.cloudflare.com/client/v4/accounts/${env.CLOUDFLARE_ACCOUNT_ID}/images/v1/stats`,
        {
          headers: { 'Authorization': `Bearer ${env.IMAGES_API_TOKEN}` }
        }
      );
      const countData = await countResponse.json();
      total = countData.result?.count?.current || 0;
    }
    
    return new Response(JSON.stringify({
      images: data.result.images || [],
      hasMore: data.result.images.length === perPage,
      total: total
    }), {
      headers: { 
        'Content-Type': 'application/json',
        'Cache-Control': 'public, max-age=60'
      }
    });
    
  } catch (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

async function serveGallery(env) {
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
        .loading {
          text-align: center;
          padding: 40px;
          color: #666;
          display: none;
        }
        .loading.visible {
          display: block;
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
        Photos: <span id="photo-count">Loading...</span>
      </div>
      <div class="grid" id="gallery"></div>
      <div class="loading" id="loading">Loading more photos...</div>

      <script>
        let currentPage = 1;
        let isLoading = false;
        let hasMore = true;
        let totalPhotos = 0;
        let loadedPhotos = 0;

        function createCard(img) {
          const meta = img.meta || {};
          const date = new Date(img.uploaded);
          
          const card = document.createElement('div');
          card.className = 'card';
          card.innerHTML = \`
            <img 
              src="\${img.variants[0]}" 
              alt="Bird photo"
              onclick="window.open('\${img.variants[0]}', '_blank')"
              loading="lazy"
            >
            <div class="info">
              <div class="weight">Weight: \${meta.weight ? meta.weight + 'g' : 'N/A'}</div>
              <div class="meta user">\${meta.userId || 'Anonymous'}</div>
              <div class="meta">\${meta.location || 'Unknown location'}</div>
              <div class="meta">\${meta.detectionType || 'Unknown'}</div>
              <div class="meta">\${date.toLocaleDateString()} \${date.toLocaleTimeString()}</div>
            </div>
          \`;
          
          return card;
        }

        function updatePhotoCount() {
          const countText = totalPhotos > 0 
            ? \`\${loadedPhotos} / \${totalPhotos}\`
            : loadedPhotos.toString();
          document.getElementById('photo-count').textContent = countText;
        }

        async function loadImages() {
          if (isLoading || !hasMore) return;
          
          isLoading = true;
          document.getElementById('loading').classList.add('visible');
          
          try {
            const response = await fetch(\`/api/images?page=\${currentPage}\`);
            const data = await response.json();
            
            if (currentPage === 1 && data.total) {
              totalPhotos = data.total;
            }
            
            const gallery = document.getElementById('gallery');
            data.images.forEach(img => {
              gallery.appendChild(createCard(img));
              loadedPhotos++;
            });
            
            updatePhotoCount();
            
            hasMore = data.hasMore;
            currentPage++;
            
          } catch (error) {
            console.error('Failed to load images:', error);
          } finally {
            isLoading = false;
            document.getElementById('loading').classList.remove('visible');
          }
        }

        window.addEventListener('scroll', () => {
          const loading = document.getElementById('loading');
          const rect = loading.getBoundingClientRect();
          const isVisible = rect.top < window.innerHeight + 500;
          
          if (isVisible && !isLoading && hasMore) {
            loadImages();
          }
        });

        loadImages();
      </script>
    </body>
    </html>
  `;
  
  return new Response(html, {
    headers: { 
      'Content-Type': 'text/html',
      'Cache-Control': 'public, max-age=300'
    }
  });
}
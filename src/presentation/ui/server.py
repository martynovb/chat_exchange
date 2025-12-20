#!/usr/bin/env python3
"""
Simple HTTP server to run the chat viewer UI locally.
Run this script and open http://localhost:8000 in your browser.
"""

import http.server
import socketserver
import os
import json
import webbrowser
from pathlib import Path
from dotenv import load_dotenv

PORT = 8000

# Load environment variables from .env file in project root
project_root = Path(__file__).parent.parent.parent.parent
env_path = project_root / '.env'
load_dotenv(env_path)

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()
    
    def do_GET(self):
        # Handle index.html specially to inject config
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            # Read index.html
            index_path = Path(__file__).parent / 'index.html'
            with open(index_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Get Supabase config from environment variables
            supabase_url = os.getenv('SUPABASE_URL', '')
            supabase_key = os.getenv('SUPABASE_ANON_KEY', '')
            
            # Create config script with proper JavaScript string escaping
            config_script = f'''
    <!-- Supabase configuration from .env -->
    <script>
        const SUPABASE_CONFIG = {{
            url: {json.dumps(supabase_url)},
            key: {json.dumps(supabase_key)}
        }};
    </script>'''
            
            # Replace the config.js script tag with inline config
            html_content = html_content.replace(
                '<script src="config.js"></script>',
                config_script
            )
            
            self.wfile.write(html_content.encode('utf-8'))
        else:
            # Serve other files normally
            super().do_GET()

def main():
    # Change to the directory where this script is located
    os.chdir(Path(__file__).parent)
    
    # Check if .env file exists
    if not env_path.exists():
        print(f"Warning: .env file not found at {env_path}")
        print("Please create a .env file with SUPABASE_URL and SUPABASE_ANON_KEY")
        print("See .env.example for reference")
    
    Handler = MyHTTPRequestHandler
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        url = f"http://localhost:{PORT}"
        print(f"Server running at {url}")
        print(f"Open {url} in your browser")
        print("Press Ctrl+C to stop the server")
        
        # Try to open browser automatically
        try:
            webbrowser.open(url)
        except:
            pass
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")

if __name__ == "__main__":
    main()




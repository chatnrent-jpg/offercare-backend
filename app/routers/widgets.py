"""
VettedMe Widget Hosting Router

Serves the embeddable verification badge widget and demo page.

Endpoints:
- GET /widgets/badge.js - Main widget script (CDN-ready)
- GET /widgets/demo - Interactive demo page
- GET /widgets/docs - Widget documentation
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse
from pathlib import Path

router = APIRouter(
    prefix="/widgets",
    tags=["Embeddable Verification Widgets"]
)

WIDGETS_DIR = Path(__file__).resolve().parent.parent / "static" / "widgets"


@router.get(
    "/badge.js",
    response_class=FileResponse,
    summary="VettedMe Badge Widget Script",
    description="Main JavaScript file for embeddable verification badges. Use this URL in your script tags."
)
async def get_badge_script():
    """
    Serve the VettedMe badge widget script.
    
    **Usage:**
    ```html
    <div id="vettedme-badge" 
         data-passport-id="YOUR_PASSPORT_ID" 
         data-badges="IDENTITY,HEALTHCARE">
    </div>
    <script src="https://api.vettedme.ai/widgets/badge.js"></script>
    ```
    
    **CDN-Ready:**
    - Caching: 1 year (immutable)
    - Compression: Gzip/Brotli
    - CORS: Enabled for all domains
    """
    return FileResponse(
        WIDGETS_DIR / "vettedme-badge.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "Access-Control-Allow-Origin": "*",
            "X-Content-Type-Options": "nosniff"
        }
    )


@router.get(
    "/demo",
    response_class=HTMLResponse,
    summary="Widget Demo Page",
    description="Interactive demo showcasing the VettedMe badge widget in action"
)
async def get_demo_page():
    """
    Display an interactive demo of the VettedMe badge widget.
    
    **Features:**
    - Live badge examples (Healthcare, Developer, Tax Professional)
    - Click-to-verify modals
    - Integration code examples
    - Customization options
    
    **Perfect for:**
    - Testing the widget before integration
    - Showing clients/users how verification works
    - Training materials for onboarding
    """
    with open(WIDGETS_DIR / "demo.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@router.get(
    "/docs",
    response_class=HTMLResponse,
    summary="Widget Documentation",
    description="Complete integration guide for developers"
)
async def get_widget_docs():
    """
    Complete documentation for integrating the VettedMe badge widget.
    
    **Includes:**
    - Quick start guide
    - Installation instructions
    - Customization options
    - Badge type reference
    - Troubleshooting tips
    """
    docs_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VettedMe Widget Documentation</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #1F2937;
            background: #F9FAFB;
            padding: 40px 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            padding: 60px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        h1 {
            font-size: 36px;
            margin-bottom: 16px;
            color: #667eea;
        }
        h2 {
            font-size: 24px;
            margin-top: 40px;
            margin-bottom: 16px;
            color: #1F2937;
        }
        h3 {
            font-size: 18px;
            margin-top: 24px;
            margin-bottom: 12px;
            color: #4B5563;
        }
        p {
            margin-bottom: 16px;
        }
        code {
            background: #F3F4F6;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            color: #667eea;
        }
        pre {
            background: #1F2937;
            color: #F9FAFB;
            padding: 24px;
            border-radius: 8px;
            overflow-x: auto;
            margin: 16px 0;
        }
        pre code {
            background: none;
            padding: 0;
            color: #10B981;
        }
        .note {
            background: #EFF6FF;
            border-left: 4px solid #3B82F6;
            padding: 16px;
            margin: 24px 0;
            border-radius: 4px;
        }
        .warning {
            background: #FEF3C7;
            border-left: 4px solid #F59E0B;
            padding: 16px;
            margin: 24px 0;
            border-radius: 4px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin: 24px 0;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid #E5E7EB;
        }
        th {
            background: #F3F4F6;
            font-weight: 600;
        }
        a {
            color: #667eea;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 VettedMe Widget Documentation</h1>
        <p>Complete integration guide for the embeddable verification badge widget.</p>

        <h2>Quick Start</h2>
        <p>Add verified credentials to any webpage in 2 steps:</p>

        <h3>Step 1: Create your passport</h3>
        <p>Visit <a href="https://vettedme.ai/create-passport">vettedme.ai/create-passport</a> to get your unique Passport ID.</p>

        <h3>Step 2: Add the widget to your page</h3>
        <pre><code>&lt;!-- Where you want the badge to appear --&gt;
&lt;div id="vettedme-badge" 
     data-passport-id="YOUR_PASSPORT_ID" 
     data-badges="IDENTITY,HEALTHCARE"&gt;
&lt;/div&gt;

&lt;!-- Widget script (add once per page) --&gt;
&lt;script src="https://api.vettedme.ai/widgets/badge.js"&gt;&lt;/script&gt;</code></pre>

        <div class="note">
            <strong>✨ That's it!</strong> The badge will automatically render and users can click it to see your verified credentials.
        </div>

        <h2>Configuration Options</h2>

        <h3>Required Attributes</h3>
        <table>
            <thead>
                <tr>
                    <th>Attribute</th>
                    <th>Description</th>
                    <th>Example</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>data-passport-id</code></td>
                    <td>Your unique passport identifier</td>
                    <td><code>uuid-12345</code></td>
                </tr>
            </tbody>
        </table>

        <h3>Optional Attributes</h3>
        <table>
            <thead>
                <tr>
                    <th>Attribute</th>
                    <th>Description</th>
                    <th>Default</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>data-badges</code></td>
                    <td>Comma-separated list of badge types to display</td>
                    <td><code>IDENTITY</code></td>
                </tr>
            </tbody>
        </table>

        <h2>Badge Types</h2>
        <table>
            <thead>
                <tr>
                    <th>Badge Type</th>
                    <th>Description</th>
                    <th>Use Cases</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><code>IDENTITY</code></td>
                    <td>Government ID + biometric</td>
                    <td>KYC, account opening, secure logins</td>
                </tr>
                <tr>
                    <td><code>HEALTHCARE</code></td>
                    <td>State nursing licenses</td>
                    <td>Staffing, telehealth, medical platforms</td>
                </tr>
                <tr>
                    <td><code>EMPLOYMENT</code></td>
                    <td>Verified work history</td>
                    <td>Job boards, freelance platforms</td>
                </tr>
                <tr>
                    <td><code>EDUCATION</code></td>
                    <td>Verified degrees</td>
                    <td>Admissions, professional networks</td>
                </tr>
                <tr>
                    <td><code>COMPLIANCE</code></td>
                    <td>Background check</td>
                    <td>Gig economy, childcare, finance</td>
                </tr>
                <tr>
                    <td><code>DEVELOPER</code></td>
                    <td>GitHub + assessments</td>
                    <td>Engineering hiring, open-source</td>
                </tr>
                <tr>
                    <td><code>PROFESSIONAL</code></td>
                    <td>CPA, EA, Bar admission</td>
                    <td>Tax services, legal platforms</td>
                </tr>
            </tbody>
        </table>

        <h2>Integration Examples</h2>

        <h3>LinkedIn About Section</h3>
        <pre><code>John Doe | RN, BSN | Baltimore, MD

Healthcare professional with 8 years of experience...

Verified Credentials:
[Copy and paste the HTML snippet here]</code></pre>

        <h3>Upwork Profile Bio</h3>
        <pre><code>Experienced software engineer specializing in React and Node.js.

My credentials are verified by VettedMe:
[Copy and paste the HTML snippet here]

Let's build something amazing together!</code></pre>

        <h3>Personal Website Footer</h3>
        <pre><code>&lt;footer&gt;
    &lt;p&gt;© 2026 Jane Smith, CPA&lt;/p&gt;
    &lt;div id="vettedme-badge" 
         data-passport-id="your-id" 
         data-badges="IDENTITY,PROFESSIONAL"&gt;
    &lt;/div&gt;
&lt;/footer&gt;

&lt;script src="https://api.vettedme.ai/widgets/badge.js"&gt;&lt;/script&gt;</code></pre>

        <h2>Browser Support</h2>
        <p>The VettedMe widget works on all modern browsers:</p>
        <ul>
            <li>✅ Chrome 90+</li>
            <li>✅ Firefox 88+</li>
            <li>✅ Safari 14+</li>
            <li>✅ Edge 90+</li>
        </ul>

        <h2>Security & Privacy</h2>
        <div class="note">
            <p><strong>🔒 Privacy First:</strong></p>
            <ul>
                <li>You control which credentials to share</li>
                <li>No raw PII is ever exposed</li>
                <li>All credentials are cryptographically signed</li>
                <li>Verification happens via secure API</li>
            </ul>
        </div>

        <h2>Troubleshooting</h2>

        <h3>Badge not showing?</h3>
        <ol>
            <li>Check that the <code>data-passport-id</code> is correct</li>
            <li>Ensure the script tag is at the bottom of your HTML</li>
            <li>Open browser console for error messages</li>
            <li>Verify your passport is active at <a href="https://vettedme.ai/dashboard">vettedme.ai/dashboard</a></li>
        </ol>

        <h3>Badge shows but modal doesn't open?</h3>
        <ol>
            <li>Check for JavaScript errors in browser console</li>
            <li>Ensure no conflicting CSS is blocking the modal</li>
            <li>Try refreshing the page</li>
        </ol>

        <div class="warning">
            <strong>⚠️ Important:</strong> The widget script must be loaded via HTTPS in production. HTTP-only pages may have security restrictions.
        </div>

        <h2>Support</h2>
        <p>Need help? We're here for you:</p>
        <ul>
            <li>📧 Email: <a href="mailto:support@vettedme.ai">support@vettedme.ai</a></li>
            <li>💬 Discord: <a href="https://discord.gg/vettedme">discord.gg/vettedme</a></li>
            <li>📚 API Docs: <a href="https://docs.vettedme.ai">docs.vettedme.ai</a></li>
            <li>🎥 Video Tutorial: <a href="https://vettedme.ai/tutorials">vettedme.ai/tutorials</a></li>
        </ul>

        <hr style="margin: 40px 0; border: none; border-top: 1px solid #E5E7EB;">

        <p style="text-align: center; color: #6B7280;">
            Made with ❤️ by <a href="https://vettedme.ai">VettedMe.ai</a> | 
            <a href="https://vettedme.ai/terms">Terms</a> | 
            <a href="https://vettedme.ai/privacy">Privacy</a>
        </p>
    </div>
</body>
</html>
    """
    return HTMLResponse(content=docs_html)

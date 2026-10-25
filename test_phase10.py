"""
Phase 10 Frontend Verification Test
Direct test of endpoints and static template rendering.
"""
import os
from starlette.requests import Request
from app.main import landing_page, auth_page, dashboard_page, templates

def test_frontend_routes():
    # Build a mock request for Starlette templates
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
    }
    req = Request(scope)

    print("1. Testing landing_page() rendering index.html...")
    res = landing_page(req)
    assert res.status_code == 200
    body = res.body.decode("utf-8")
    assert "NyayaSetu" in body
    assert "aceternity.css" in body
    assert "perspective-container" in body
    assert "hero-scaled-card" in body
    print("   [PASS] Landing page renders Aceternity Hero & 3D Perspective mockup.")

    print("2. Testing auth_page() rendering auth.html...")
    res_auth = auth_page(req)
    assert res_auth.status_code == 200
    auth_body = res_auth.body.decode("utf-8")
    assert "Role-Based Access Control" in auth_body
    assert "One-Click Role Demo Sign In" in auth_body
    assert "judge_sharma" in auth_body
    print("   [PASS] Split Auth page renders with RBAC demo selector pills.")

    print("3. Testing dashboard_page() rendering dashboard.html...")
    res_dash = dashboard_page(req)
    assert res_dash.status_code == 200
    dash_body = res_dash.body.decode("utf-8")
    assert "dashboard.js" in dash_body
    assert "Virtual Courtroom" in dash_body
    assert "AI Scheduling Studio" in dash_body
    print("   [PASS] Dashboard page renders with actor sections and WebSocket display.")

    print("4. Testing Static CSS Asset presence...")
    css_path = os.path.join("static", "css", "aceternity.css")
    assert os.path.exists(css_path)
    with open(css_path, "r", encoding="utf-8") as f:
        css = f.read()
    assert ".hero-scaled-card" in css
    assert ".radial-glow-blue" in css
    print("   [PASS] aceternity.css verified.")

    print("5. Testing Static JS Assets presence...")
    api_js = os.path.join("static", "js", "api.js")
    dash_js = os.path.join("static", "js", "dashboard.js")
    assert os.path.exists(api_js)
    assert os.path.exists(dash_js)
    with open(api_js, "r", encoding="utf-8") as f:
        js1 = f.read()
    with open(dash_js, "r", encoding="utf-8") as f:
        js2 = f.read()
    assert "CourtWebSocket" in js1
    assert "applyRoleVisibility" in js2
    assert "switchDemoRole" in js2
    print("   [PASS] api.js and dashboard.js verified.")

    print("\n=======================================================")
    print("ALL PHASE 10 FRONTEND INTEGRATION TESTS PASSED 100%!")
    print("=======================================================")

if __name__ == "__main__":
    test_frontend_routes()

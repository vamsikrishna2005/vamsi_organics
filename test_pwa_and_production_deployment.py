"""
Unit & Integration Tests for PWA and Cloud Production Deployment Package
"""
import unittest
import json
import os
import sqlite3
from PIL import Image
from app import app, OTP_STORE
import database

class TestPWAAndProductionDeployment(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.client = self.app.test_client()

    def test_01_manifest_json_structure(self):
        """Verify static/manifest.json is valid and conforms to W3C Web App Manifest spec"""
        manifest_path = os.path.join(r"C:\vamsi_vegi_market", "static", "manifest.json")
        self.assertTrue(os.path.exists(manifest_path), "manifest.json does not exist")
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        self.assertTrue("PPM" in manifest.get("name", "") or "Vamsi" in manifest.get("name", ""))
        self.assertIn("short_name", manifest)
        self.assertEqual(manifest.get("display"), "standalone")
        self.assertEqual(manifest.get("start_url"), "/dashboard?tab=market")
        self.assertEqual(manifest.get("theme_color"), "#065f46")
        self.assertEqual(manifest.get("background_color"), "#f2f9f1")
        
        # Verify icons
        icons = manifest.get("icons", [])
        self.assertGreaterEqual(len(icons), 2)
        sizes = [icon.get("sizes") for icon in icons]
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)

    def test_02_service_worker_asset(self):
        """Verify static/service-worker.js exists and has core caching logic"""
        sw_path = os.path.join(r"C:\vamsi_vegi_market", "static", "service-worker.js")
        self.assertTrue(os.path.exists(sw_path), "service-worker.js does not exist")
        
        with open(sw_path, "r", encoding="utf-8") as f:
            sw_code = f.read()
            
        self.assertTrue("ppm-vegi-cache" in sw_code or "vamsi-vegi-cache" in sw_code)
        self.assertIn("install", sw_code)
        self.assertIn("fetch", sw_code)
        self.assertIn("caches.open", sw_code)

    def test_03_pwa_icon_images(self):
        """Verify physical PNG icon files exist with proper dimensions"""
        icons_dir = os.path.join(r"C:\vamsi_vegi_market", "static", "icons")
        self.assertTrue(os.path.exists(icons_dir), "static/icons directory does not exist")
        
        expected_icons = {
            "icon-192.png": (192, 192),
            "icon-512.png": (512, 512),
            "apple-touch-icon.png": (180, 180)
        }
        
        for filename, expected_size in expected_icons.items():
            file_path = os.path.join(icons_dir, filename)
            self.assertTrue(os.path.exists(file_path), f"{filename} missing")
            with Image.open(file_path) as img:
                self.assertEqual(img.size, expected_size, f"{filename} size is {img.size}, expected {expected_size}")
                self.assertEqual(img.format, "PNG", f"{filename} is not a valid PNG")

    def test_04_base_template_pwa_integration(self):
        """Verify templates/base.html has manifest link, meta tags, and registration script"""
        base_path = os.path.join(r"C:\vamsi_vegi_market", "templates", "base.html")
        with open(base_path, "r", encoding="utf-8") as f:
            html = f.read()
            
        self.assertIn('rel="manifest"', html)
        self.assertIn('/static/manifest.json', html)
        self.assertIn('meta name="theme-color" content="#065f46"', html)
        self.assertIn('apple-touch-icon', html)
        self.assertIn('serviceWorker.register', html)

    def test_05_production_deployment_files(self):
        """Verify all production deployment files exist and contain appropriate configurations"""
        base_dir = r"C:\vamsi_vegi_market"
        
        # 1. requirements.txt
        req_path = os.path.join(base_dir, "requirements.txt")
        self.assertTrue(os.path.exists(req_path))
        with open(req_path, "r", encoding="utf-8") as f:
            req_content = f.read()
            self.assertIn("Flask", req_content)
            self.assertIn("gunicorn", req_content)
            
        # 2. Procfile
        procfile_path = os.path.join(base_dir, "Procfile")
        self.assertTrue(os.path.exists(procfile_path))
        with open(procfile_path, "r", encoding="utf-8") as f:
            proc_content = f.read()
            self.assertIn("web: gunicorn wsgi:app", proc_content)
            
        # 3. wsgi.py
        wsgi_path = os.path.join(base_dir, "wsgi.py")
        self.assertTrue(os.path.exists(wsgi_path))
        with open(wsgi_path, "r", encoding="utf-8") as f:
            wsgi_content = f.read()
            self.assertIn("from app import app", wsgi_content)
            
        # 4. render.yaml
        render_path = os.path.join(base_dir, "render.yaml")
        self.assertTrue(os.path.exists(render_path))
        with open(render_path, "r", encoding="utf-8") as f:
            render_content = f.read()
            self.assertIn("services:", render_content)
            self.assertTrue("vamsi-organics" in render_content or "vamsi-vegi-market" in render_content)
            self.assertIn("gunicorn wsgi:app", render_content)
            
        # 5. Dockerfile
        docker_path = os.path.join(base_dir, "Dockerfile")
        self.assertTrue(os.path.exists(docker_path))
        with open(docker_path, "r", encoding="utf-8") as f:
            docker_content = f.read()
            self.assertIn("FROM python:", docker_content)
            self.assertIn("EXPOSE 5000", docker_content)
            self.assertIn("gunicorn", docker_content)

    def test_06_otp_send_and_verify_endpoints(self):
        """Verify SMS OTP generation, validation, and session login for customers"""
        # Bad phone format
        res_bad = self.client.post('/api/auth/send-otp', json={'phone': '123'})
        self.assertEqual(res_bad.status_code, 400)
        
        # Valid customer phone (Vamsi Vegi demo account: 8888888888 or test phone)
        test_phone = '9876543210'
        res_send = self.client.post('/api/auth/send-otp', json={'phone': test_phone})
        self.assertEqual(res_send.status_code, 200)
        data = res_send.get_json()
        self.assertEqual(data.get('status'), 'success')
        self.assertIn(test_phone, OTP_STORE)
        
        generated_otp = OTP_STORE[test_phone]['otp']
        self.assertEqual(len(generated_otp), 6)
        
        # Bad OTP verification
        res_bad_otp = self.client.post('/api/auth/verify-otp', json={'phone': test_phone, 'otp': '000000'})
        self.assertEqual(res_bad_otp.status_code, 400)
        
        # Correct OTP verification for existing customer
        conn = sqlite3.connect(database.DB_PATH)
        conn.row_factory = sqlite3.Row
        existing_cust = conn.execute("SELECT * FROM users WHERE role = 'customer' LIMIT 1").fetchone()
        conn.close()
        
        if existing_cust:
            cust_phone = existing_cust['phone']
            # Send OTP to real customer
            self.client.post('/api/auth/send-otp', json={'phone': cust_phone})
            cust_otp = OTP_STORE[cust_phone]['otp']
            
            # Verify OTP
            res_verify = self.client.post('/api/auth/verify-otp', json={'phone': cust_phone, 'otp': cust_otp})
            self.assertEqual(res_verify.status_code, 200)
            verify_data = res_verify.get_json()
            self.assertEqual(verify_data.get('status'), 'success')
            self.assertIn('redirect_url', verify_data)

    def test_07_admin_isolation_from_otp_login(self):
        """Ensure Admin accounts cannot bypass credentials using OTP"""
        conn = sqlite3.connect(database.DB_PATH)
        conn.row_factory = sqlite3.Row
        admin_user = conn.execute("SELECT * FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        conn.close()
        
        if admin_user and admin_user['phone']:
            admin_phone = admin_user['phone']
            self.client.post('/api/auth/send-otp', json={'phone': admin_phone})
            admin_otp = OTP_STORE[admin_phone]['otp']
            
            res = self.client.post('/api/auth/verify-otp', json={'phone': admin_phone, 'otp': admin_otp})
            # Admin must be denied consumer OTP login
            self.assertEqual(res.status_code, 403)

if __name__ == '__main__':
    unittest.main()

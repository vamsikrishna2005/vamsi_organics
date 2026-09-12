import unittest
from app import app
from database import init_db, get_db_connection

class TestAddressManagement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        # Login as customer Vamsi Vegi (Phone 8888888888)
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

    def test_01_get_saved_addresses_returns_default(self):
        """Verify customer receives their list of saved addresses with default flagged."""
        res = self.app.get('/api/user/addresses')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(len(data['addresses']), 0)
        self.assertIsNotNone(data['default_address'])
        self.assertTrue(data['default_address']['is_default'])

    def test_02_save_new_address_as_default(self):
        """Verify customer can add a new address and set it as default."""
        new_addr_payload = {
            "label": "Farmhouse",
            "address": "Survey 44, Shankarpally Road, Hyderabad - 501203",
            "is_default": True
        }
        save_res = self.app.post('/api/user/save-address', json=new_addr_payload)
        self.assertEqual(save_res.status_code, 200)
        self.assertTrue(save_res.get_json()['success'])

        # Verify new default address
        get_res = self.app.get('/api/user/addresses')
        data = get_res.get_json()
        self.assertEqual(data['default_address']['label'], "Farmhouse")
        self.assertEqual(data['default_address']['address'], new_addr_payload['address'])

    def test_03_switch_default_address(self):
        """Verify customer can switch default address."""
        # Get addresses
        get_res = self.app.get('/api/user/addresses')
        addresses = get_res.get_json()['addresses']
        non_default = [a for a in addresses if not a['is_default']][0]

        switch_res = self.app.post('/api/user/set-default-address', json={
            "address_id": non_default['id']
        })
        self.assertEqual(switch_res.status_code, 200)
        self.assertTrue(switch_res.get_json()['success'])

        # Verify switched
        re_get = self.app.get('/api/user/addresses')
        self.assertEqual(re_get.get_json()['default_address']['id'], non_default['id'])

    def test_04_checkout_requires_address(self):
        """Verify checkout fails if delivery address is empty."""
        bad_order = {
            "items": [{"product_id": 1, "quantity": 1}],
            "delivery_date": "2026-09-05",
            "delivery_slot": "Morning (8:00 AM - 11:00 AM)",
            "delivery_address": "" # Empty
        }
        res = self.app.post('/api/checkout', json=bad_order)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])

    def test_05_checkout_with_address_and_save_as_default(self):
        """Verify checkout saves new delivery address to user's address book."""
        checkout_order = {
            "items": [{"product_id": 1, "quantity": 2}],
            "delivery_date": "2026-09-05",
            "delivery_slot": "Morning (8:00 AM - 11:00 AM)",
            "delivery_address": "Villa 108, Palm Meadows, Kondapur, Hyderabad - 500084",
            "save_as_default": True
        }
        res = self.app.post('/api/checkout', json=checkout_order)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Verify address is now saved and set as default
        addr_res = self.app.get('/api/user/addresses')
        default_addr = addr_res.get_json()['default_address']
        self.assertIn("Villa 108, Palm Meadows", default_addr['address'])

if __name__ == '__main__':
    unittest.main()

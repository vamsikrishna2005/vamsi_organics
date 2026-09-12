import unittest
from app import app
from database import init_db, get_db_connection

class TestAdvancedCommercialFeatures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        self.app.post('/login', data={'login_type': 'customer', 'phone': '8888888888'}, follow_redirects=True)

    def test_01_wallet_api(self):
        res = self.app.get('/api/user/wallet')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('balance', data)
        self.assertGreaterEqual(data['balance'], 0.0)
        self.assertIn('transactions', data)
        self.assertIsInstance(data['transactions'], list)

    def test_02_product_details_nutrition_api(self):
        res = self.app.get('/api/product/1/details')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('product', data)
        self.assertIn('Tomato', data['product']['name'])
        self.assertIn('nutrition', data)
        self.assertIn('calories', data['nutrition'])
        self.assertIn('benefits', data['nutrition'])
        self.assertIn('culinary_use', data['nutrition'])
        self.assertIn('reviews', data)
        self.assertIsInstance(data['reviews'], list)

    def test_03_product_review_submission(self):
        res = self.app.post('/api/product/review', json={
            'product_id': 2,
            'rating': 5.0,
            'comment': 'Exceptionally sweet and tender fresh onions! Best farm quality in town.'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('average_rating', data)
        self.assertIn('review_count', data)
        self.assertGreaterEqual(data['review_count'], 1)

        err_res = self.app.post('/api/product/review', json={
            'product_id': 2,
            'rating': 6.0,
            'comment': 'Too high'
        })
        self.assertEqual(err_res.status_code, 400)
        self.assertFalse(err_res.get_json()['success'])

        err_res2 = self.app.post('/api/product/review', json={
            'product_id': 2,
            'rating': 4.0,
            'comment': '   '
        })
        self.assertEqual(err_res2.status_code, 400)

    def test_04_checkout_with_wallet_and_cashback(self):
        conn = get_db_connection()
        conn.execute("UPDATE users SET wallet_balance = 100.0 WHERE phone = '8888888888'")
        conn.commit()
        conn.close()

        checkout_payload = {
            'items': [{'product_id': 1, 'quantity': 2}],
            'delivery_date': '2026-09-12',
            'delivery_slot': 'Morning (8:00 AM - 11:00 AM)',
            'delivery_address': 'Plot 120, Road 36, Jubilee Hills, Hyderabad',
            'save_as_default': True,
            'coupon_code': '',
            'discount_amount': 0.0,
            'redeem_wallet': True,
            'wallet_redeem_amount': 30.0
        }

        res = self.app.post('/api/checkout', json=checkout_payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['gross_total'], 70.0)
        self.assertEqual(data['wallet_deducted'], 30.0)
        self.assertEqual(data['grand_total'], 40.0)
        self.assertEqual(data['cashback_earned'], 2.00)

        wallet_res = self.app.get('/api/user/wallet')
        self.assertEqual(wallet_res.status_code, 200)
        wallet_data = wallet_res.get_json()
        self.assertAlmostEqual(wallet_data['balance'], 72.0, places=2)

        tx_types = [t['type'] for t in wallet_data['transactions']]
        self.assertIn('debit', tx_types)
        self.assertIn('credit', tx_types)

    def test_05_unauthorized_access(self):
        guest_client = app.test_client()
        guest_client.testing = True

        res1 = guest_client.get('/api/user/wallet')
        self.assertEqual(res1.status_code, 401)

        res2 = guest_client.post('/api/product/review', json={'product_id': 1, 'rating': 5, 'comment': 'Hi'})
        self.assertEqual(res2.status_code, 401)

if __name__ == '__main__':
    unittest.main()

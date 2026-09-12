import unittest
import sqlite3
import os
import database
import recommender

class TestVegiRecommender(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Initialize and seed database for testing
        database.init_db()

    def test_database_connection(self):
        """Test if database setup populated tables correctly"""
        conn = database.get_db_connection()
        products = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        purchases = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        conn.close()
        
        self.assertGreater(products, 0, "Products should be seeded")
        self.assertGreater(users, 0, "Users should be seeded")
        self.assertGreater(purchases, 0, "Purchases should be seeded")

    def test_user_recommendations(self):
        """Test if recommendations contain relevant content-based logic"""
        # User 1 (Vamsi Vegi) has a history of buying Spinach and Coriander
        recs = recommender.get_ai_recommendations(user_id=1, limit=3)
        self.assertGreater(len(recs), 0, "Should generate recommendations")
        
        # Verify recommended items are dictionaries with product info
        first_rec = recs[0]
        self.assertIn("product", first_rec)
        self.assertIn("reason", first_rec)
        
        # User 1 bought green leafy greens, so other green/leafy herbs (e.g. mint) should score high or show up
        recommended_names = [r["product"]["name"] for r in recs]
        # Let's inspect recommendation reasons
        reasons = [r["reason"] for r in recs]
        
        print("\n[TEST INFO] User 1 Recommendations:")
        for r in recs:
            safe_name = r['product']['name'].encode('ascii', 'replace').decode('ascii')
            print(f"- {safe_name}: {r['reason']} (Score: {r['score']:.2f})")

        self.assertTrue(any("interest in" in reason or "Similar to" in reason or "bought" in reason or "Highly recommended" in reason for reason in reasons), 
                        "AI reason should indicate content-based tags or collaborative matching")

    def test_predictive_notifications(self):
        """Test if restock prediction identifies items nearing end of lifespan"""
        # User 1 bought spinach 6 days ago. Leafy greens have a 7-day lifespan.
        # This is 85% of lifespan (6/7 = 85.7%). It should trigger an alert.
        alerts = recommender.get_predictive_notifications(user_id=1)
        
        print("\n[TEST INFO] User 1 Predictive Alerts:")
        for a in alerts:
            safe_pname = a['product_name'].encode('ascii', 'replace').decode('ascii')
            safe_msg = a['message'].encode('ascii', 'ignore').decode('ascii')
            print(f"- Alert for {safe_pname}: {safe_msg}")

        self.assertGreater(len(alerts), 0, "User 1 should have predictive restock warnings")
        product_names = [a["product_name"] for a in alerts]
        self.assertTrue(any("Spinach" in name for name in product_names), "Should flag Spinach as runout warning")

    def test_admin_restock_alerts(self):
        """Test that restocking triggers notifications for buyers of a product"""
        conn = database.get_db_connection()
        # Find who has Spinach purchases
        spinach_buyers_before = conn.execute("""
            SELECT COUNT(*) FROM notifications n
            JOIN users u ON n.user_id = u.id
            WHERE n.message LIKE '%Spinach%is newly harvested%'
        """).fetchone()[0]
        conn.close()

        # Trigger restock notification on Spinach (Product ID 9)
        notified = recommender.trigger_restock_notification(product_id=9)
        self.assertGreater(notified, 0, "Should dispatch notifications to past Spinach buyers")

        conn = database.get_db_connection()
        spinach_buyers_after = conn.execute("""
            SELECT COUNT(*) FROM notifications n
            JOIN users u ON n.user_id = u.id
            WHERE n.message LIKE '%Spinach%is newly harvested%'
        """).fetchone()[0]
        conn.close()

        self.assertGreater(spinach_buyers_after, spinach_buyers_before, "Notifications database records should increase")

if __name__ == '__main__':
    unittest.main()

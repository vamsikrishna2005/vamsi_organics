# 🥬 PPM Organic Farms - Smart Farm-to-Table E-Commerce Platform & Mobile App (PWA)

An e-commerce marketplace and Progressive Web Application (PWA) for daily farm-fresh vegetable deliveries, featuring Cash on Delivery (COD), 24/7 Kisan AI assistant, unique phone-authenticated customer profiles, and a Customer 360° Admin Management Console.

---

## 🌟 Key Features

- 📱 **Progressive Web App (PWA)**: Installable on Android, iOS, Windows, and macOS with offline caching.
- 💵 **100% Cash on Delivery (COD)**: Safe and familiar local checkout workflow.
- 🌾 **Kisan AI Smart Chatbot**: Bilingual (English + Telugu) assistant for vegetable inquiries, Telugu recipe suggestions, order tracking, and live WhatsApp escalation.
- 🪙 **Farm Wallet & 5% Cashback**: Automatic cashback credited on every delivery, redeemable directly on future orders.
- 🛡️ **Unique Customer Identification**: Unique mobile number and address verification.
- 📊 **Store Manager Operations & Customer 360° CRM**: Real-time order dispatch queue, inventory tracking, customer analytics, and one-click WhatsApp contact.
- 🔒 **Official Legal Compliance**: Built-in Privacy Policy page (`/privacy-policy`) compliant with Google Play requirements.

---

## 🚀 Cloud Deployment (Render / Heroku / Railway)

This repository includes turnkey deployment configuration:
- `render.yaml` - 1-click blueprint for Render.com
- `Procfile` - Production WSGI worker declaration (`web: gunicorn wsgi:app`)
- `wsgi.py` - WSGI entry point
- `Dockerfile` - Containerized deployment

### Quick Deploy to Render:
1. Connect this GitHub repository on [Render.com](https://render.com).
2. Choose **Web Service**.
3. Render will auto-detect Python, install `requirements.txt`, and start the Gunicorn WSGI server.

---

## 📲 Google Play Store Packaging

Use [PWABuilder.com](https://www.pwabuilder.com) to generate an Android App Bundle (`.aab`) directly from your deployed URL for publishing to the Google Play Console.

---

## 📞 Support & Helpline

- **Helpline Phone**: +91 76759 60440
- **WhatsApp Support**: [+91 76759 60440](https://wa.me/917675960440)

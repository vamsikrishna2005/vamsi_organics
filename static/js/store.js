// PPM Organic Farms - Frontend Store, Invoicing, Cart, Address Manager, Coupons, and Real-Time Admin Alerts

let cart = [];
let userAddresses = [];
let currentSelectedAddress = null;
let appliedCoupon = null;
let currentActiveInvoice = null;

// New Commercial Feature States: Farm Wallet & Voice Search
let isWalletApplied = false;
let userWalletBalance = 100.0;
let walletDeductedAmount = 0.0;
let speechRecognitionInstance = null;
let isListeningVoice = false;

// Initialize Cart on Load, Saved Address, Wallet & Admin Live Polling
document.addEventListener("DOMContentLoaded", () => {
    loadCartFromLocalStorage();
    updateCartUI();
    
    // Ensure search input starts completely empty and not filled by browser autofill
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.value = "";
    }

    // Initialize customer saved & default delivery addresses
    initDeliveryAddress();

    // Fetch customer Farm Wallet balance & 5% cashback coin passbook
    fetchUserWalletBalance();
    
    // Check if on storefront to wire click handlers
    const addToCartBtns = document.querySelectorAll(".add-to-cart-btn");
    addToCartBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const product = {
                id: parseInt(btn.dataset.id),
                name: btn.dataset.name,
                price: parseFloat(btn.dataset.price),
                unit: btn.dataset.unit,
                image: btn.dataset.image,
                stock: parseInt(btn.dataset.stock)
            };
            addToCart(product);
        });
    });

    // Start Live Admin Polling across any page if logged in as admin/manager
    const userRole = document.querySelector('meta[name="user-role"]')?.content;
    if (userRole === 'admin' || window.location.pathname.startsWith("/admin")) {
        startAdminLiveOrderPolling();
    }

    // Wire real-time unique phone & email availability checkers on registration forms
    initUniqueCredentialCheckers();

    // Wire logout links to immediately clear in-memory cart and guest storage
    document.querySelectorAll('a[href="/logout"]').forEach(el => {
        el.addEventListener("click", () => {
            cart = [];
            localStorage.removeItem("vegi_market_cart_guest");
        });
    });

    // Initialize Progressive Web App (PWA) 1-click install prompt and badges
    initPwaInstaller();
});

// Fetch and initialize customer's saved default delivery address
async function initDeliveryAddress() {
    const addressInput = document.getElementById("delivery-address");
    const labelEl = document.getElementById("cart-selected-address-label");
    const textEl = document.getElementById("cart-selected-address-text");
    
    try {
        const response = await fetch("/api/user/addresses");
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.addresses && data.addresses.length > 0) {
                userAddresses = data.addresses;
                const defAddr = data.default_address || data.addresses[0];
                currentSelectedAddress = defAddr;
                
                if (addressInput) addressInput.value = defAddr.address;
                if (labelEl) labelEl.innerText = `${defAddr.label} ${defAddr.is_default ? '(Default)' : ''}`;
                if (textEl) textEl.innerText = defAddr.address;
                localStorage.setItem("vof_customer_address", defAddr.address);
                return;
            }
        }
    } catch (e) {}

    // Local Storage Fallback
    const savedAddress = localStorage.getItem("vof_customer_address");
    if (savedAddress && savedAddress.trim() !== "") {
        if (addressInput) addressInput.value = savedAddress;
        if (labelEl) labelEl.innerText = "Saved Address";
        if (textEl) textEl.innerText = savedAddress;
    } else {
        if (textEl) textEl.innerText = "Click to set delivery address";
        if (labelEl) labelEl.innerText = "Set Address";
    }
}

// Dynamic per-user cart storage key
function getCartStorageKey() {
    const userId = document.querySelector('meta[name="user-id"]')?.content;
    const userRole = document.querySelector('meta[name="user-role"]')?.content;
    
    // Store managers/admins do not mix with customer carts
    if (userRole === 'admin') {
        return 'vegi_market_cart_admin';
    }
    if (userId && userId.trim() !== '') {
        return `vegi_market_cart_user_${userId.trim()}`;
    }
    return 'vegi_market_cart_guest';
}

// Sync cart with backend database
let cartSyncTimeout = null;
function syncCartWithServer() {
    const userId = document.querySelector('meta[name="user-id"]')?.content;
    if (!userId || userId.trim() === '') return;
    
    clearTimeout(cartSyncTimeout);
    cartSyncTimeout = setTimeout(async () => {
        try {
            await fetch("/api/cart/sync", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ items: cart })
            });
        } catch (e) {
            console.error("Failed to sync cart with server:", e);
        }
    }, 300);
}

// Fetch user's persistent cart from server on load
async function fetchUserCartFromServer() {
    const userId = document.querySelector('meta[name="user-id"]')?.content;
    if (!userId || userId.trim() === '') return;
    
    try {
        const response = await fetch("/api/cart");
        if (response.ok) {
            const data = await response.json();
            if (data.success && Array.isArray(data.items)) {
                // If local cart is empty but server has items, load from server
                if (cart.length === 0 && data.items.length > 0) {
                    cart = data.items;
                    saveCartToLocalStorage(false);
                    updateCartUI();
                } else if (cart.length > 0) {
                    // Sync current local items to server
                    syncCartWithServer();
                }
            }
        }
    } catch (e) {
        console.error("Error fetching cart from server:", e);
    }
}

// Load cart state
function loadCartFromLocalStorage() {
    const currentKey = getCartStorageKey();
    const userId = document.querySelector('meta[name="user-id"]')?.content;
    
    // 1. If customer just logged in, check if there are guest cart items to migrate
    if (userId && userId.trim() !== '') {
        const guestCartStr = localStorage.getItem("vegi_market_cart_guest");
        if (guestCartStr) {
            try {
                const guestCart = JSON.parse(guestCartStr);
                if (Array.isArray(guestCart) && guestCart.length > 0) {
                    const existingUserCart = JSON.parse(localStorage.getItem(currentKey) || "[]");
                    // Merge guest items into user cart
                    guestCart.forEach(gItem => {
                        const idx = existingUserCart.findIndex(it => it.id === gItem.id);
                        if (idx !== -1) {
                            existingUserCart[idx].quantity += gItem.quantity;
                        } else {
                            existingUserCart.push(gItem);
                        }
                    });
                    localStorage.setItem(currentKey, JSON.stringify(existingUserCart));
                    localStorage.removeItem("vegi_market_cart_guest");
                }
            } catch (e) {}
        }
    }

    // 2. Load from user's isolated storage
    const savedCart = localStorage.getItem(currentKey);
    if (savedCart) {
        try {
            cart = JSON.parse(savedCart);
        } catch (e) {
            cart = [];
        }
    } else {
        cart = [];
    }
    
    // 3. Reconcile with server if logged in
    fetchUserCartFromServer();
}

// Save cart state
function saveCartToLocalStorage(shouldSync = true) {
    const currentKey = getCartStorageKey();
    localStorage.setItem(currentKey, JSON.stringify(cart));
    if (shouldSync) {
        syncCartWithServer();
    }
}

// Toast System
function showToast(message, type = "success") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `flex items-center w-full max-w-xs p-4 text-gray-900 rounded-lg shadow-lg border pointer-events-auto transition-all duration-300 transform translate-x-full ${
        type === "success" ? "bg-green-50 border-green-200 text-green-800" : 
        type === "error" ? "bg-red-50 border-red-200 text-red-800" : "bg-blue-50 border-blue-200 text-blue-800"
    }`;
    
    const icon = type === "success" ? "fa-circle-check text-green-500" : 
                 type === "error" ? "fa-triangle-exclamation text-red-500" : "fa-circle-info text-blue-500";
    
    toast.innerHTML = `
        <div class="inline-flex items-center justify-center flex-shrink-0 w-8 h-8 rounded-lg">
            <i class="fa-solid ${icon} text-lg"></i>
        </div>
        <div class="ml-3 text-sm font-semibold">${message}</div>
        <button type="button" class="ml-auto -mx-1.5 -my-1.5 bg-transparent text-gray-400 hover:text-gray-900 rounded-lg focus:ring-2 focus:ring-gray-300 p-1.5 inline-flex h-8 w-8" onclick="this.parentElement.remove()">
            <i class="fa-solid fa-xmark"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // Slide in
    setTimeout(() => {
        toast.classList.remove("translate-x-full");
    }, 10);

    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.classList.add("translate-x-full");
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Add Item to Cart (Generic)
function addToCart(product) {
    const existingIndex = cart.findIndex(item => item.id === product.id);
    
    const cartQty = existingIndex !== -1 ? cart[existingIndex].quantity : 0;
    if (cartQty + 1 > product.stock) {
        showToast(`Sorry, only ${product.stock} units of ${product.name} in stock!`, "error");
        return;
    }

    if (existingIndex !== -1) {
        cart[existingIndex].quantity += 1;
    } else {
        cart.push({ ...product, quantity: 1 });
    }
    
    saveCartToLocalStorage();
    updateCartUI();
    showToast(`Added ${product.name} to basket!`);
}

// Real-Time Counter Add/Remove directly from Product Cards
function addToCartRealtime(productId, delta = 1) {
    const actionEl = document.querySelector(`.product-card-action[data-id="${productId}"]`);
    
    let product;
    if (actionEl) {
        product = {
            id: parseInt(actionEl.dataset.id),
            name: actionEl.dataset.name,
            price: parseFloat(actionEl.dataset.price),
            unit: actionEl.dataset.unit,
            image: actionEl.dataset.icon,
            stock: parseInt(actionEl.dataset.stock)
        };
    } else {
        const item = cart.find(i => i.id === productId);
        if (!item) return;
        product = { ...item };
    }
    
    const existingIndex = cart.findIndex(item => item.id === product.id);
    
    if (delta > 0) {
        const currentQty = existingIndex !== -1 ? cart[existingIndex].quantity : 0;
        if (currentQty + 1 > product.stock) {
            showToast(`Sorry, only ${product.stock} units available in stock!`, "error");
            return;
        }
        if (existingIndex !== -1) {
            cart[existingIndex].quantity += 1;
        } else {
            cart.push({ ...product, quantity: 1 });
        }
    } else {
        if (existingIndex !== -1) {
            cart[existingIndex].quantity += delta;
            if (cart[existingIndex].quantity <= 0) {
                cart.splice(existingIndex, 1);
            }
        }
    }
    
    saveCartToLocalStorage();
    updateCartUI();
}

// Change item quantity in cart drawer
function changeQuantity(productId, delta) {
    addToCartRealtime(productId, delta);
}

// Modal Body Scroll Lock Helper (prevents background scrolling when any drawer/modal is open)
function setModalScrollLock(isOpen) {
    if (isOpen) {
        document.body.classList.add("modal-open");
    } else {
        const anyModalOpen = document.querySelector("#order-success-modal:not(.hidden), #address-modal:not(.hidden), #new-address-modal:not(.hidden), #new-order-popup-modal:not(.hidden), #produce-detail-modal:not(.hidden), #invoice-modal:not(.hidden), #review-modal:not(.hidden), #admin-order-drawer-backdrop:not(.hidden)");
        if (!anyModalOpen) {
            document.body.classList.remove("modal-open");
        }
    }
}

// Toggle Shopping Cart Drawer
function toggleCartDrawer() {
    const drawer = document.getElementById("cart-drawer");
    if (drawer) {
        const isOpening = drawer.classList.contains("translate-x-full");
        drawer.classList.toggle("translate-x-full");
        setModalScrollLock(isOpening);
    }
}

// Update Cart Badge, Drawer UI, Standalone Cart Page, and Sync Product Card Counter Buttons
function updateCartUI() {
    const badge = document.getElementById("cart-badge-count");
    const mobileBadge = document.getElementById("mobile-cart-badge");
    const totalCount = cart.reduce((sum, item) => sum + item.quantity, 0);
    
    if (badge) {
        badge.innerText = totalCount;
        if (totalCount > 0) {
            badge.classList.remove("hidden");
        } else {
            badge.classList.add("hidden");
        }
    }

    if (mobileBadge) {
        mobileBadge.innerText = totalCount;
    }
    
    // Update dashboard app bar basket count badges
    const tabBadge = document.getElementById("tab-basket-count-badge");
    if (tabBadge) {
        tabBadge.innerText = totalCount;
        if (totalCount > 0) tabBadge.classList.remove("hidden");
        else tabBadge.classList.add("hidden");
    }

    const quickCount = document.getElementById("quick-bar-basket-count");
    if (quickCount) {
        quickCount.innerText = totalCount;
    }
    
    // Update storefront inline summary
    const storeCount = document.getElementById("storefront-cart-count");
    if (storeCount) {
        storeCount.innerText = totalCount;
    }

    // 1. Sync Product Card Counters in Real-Time
    document.querySelectorAll(".product-card-action").forEach(actionEl => {
        const id = parseInt(actionEl.dataset.id);
        const wrapper = document.getElementById(`cart-btn-wrapper-${id}`);
        if (!wrapper) return;
        
        const cartItem = cart.find(i => i.id === id);
        if (cartItem && cartItem.quantity > 0) {
            wrapper.innerHTML = `
                <div class="flex items-center bg-emerald-600 text-white rounded-xl shadow-sm overflow-hidden select-none">
                    <button onclick="addToCartRealtime(${id}, -1)" class="px-2.5 py-1.5 hover:bg-emerald-700 font-extrabold text-xs transition active:scale-90">-</button>
                    <span class="px-2 font-extrabold text-xs text-white min-w-[20px] text-center">${cartItem.quantity}</span>
                    <button onclick="addToCartRealtime(${id}, 1)" class="px-2.5 py-1.5 hover:bg-emerald-700 font-extrabold text-xs transition active:scale-90">+</button>
                </div>
            `;
        } else {
            wrapper.innerHTML = `
                <button onclick="addToCartRealtime(${id}, 1)" class="bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs px-3.5 py-2 rounded-xl transition duration-150 inline-flex items-center space-x-1 shadow-sm shadow-emerald-600/20 active:scale-95">
                    <i class="fa-solid fa-plus text-[10px]"></i>
                    <span>ADD</span>
                </button>
            `;
        }
    });

    // 2. Compute Cart Financials (Subtotal, Discount, Wallet, Net Total)
    let subtotal = 0;
    cart.forEach(item => {
        subtotal += item.price * item.quantity;
    });

    let discount = 0.0;
    if (appliedCoupon && cart.length > 0) {
        discount = appliedCoupon.discount || 0.0;
    }

    const remainingAfterCoupon = Math.max(0.0, subtotal - discount);
    if (isWalletApplied && userWalletBalance > 0 && cart.length > 0) {
        walletDeductedAmount = Math.min(userWalletBalance, remainingAfterCoupon);
    } else {
        walletDeductedAmount = 0.0;
    }

    const finalTotal = Math.max(0.0, remainingAfterCoupon - walletDeductedAmount);

    // Update financial elements across both /shop and /cart
    const cartSubtotalEls = document.querySelectorAll("#cart-subtotal");
    cartSubtotalEls.forEach(el => el.innerText = `₹${subtotal.toFixed(2)}`);

    const finalTotalEls = document.querySelectorAll("#cart-final-total");
    finalTotalEls.forEach(el => el.innerText = `₹${finalTotal.toFixed(2)}`);

    const discountRows = document.querySelectorAll("#cart-discount-row");
    const discountVals = document.querySelectorAll("#cart-discount-val");
    const couponBadges = document.querySelectorAll("#coupon-applied-badge");
    const couponNameEls = document.querySelectorAll("#applied-coupon-name");

    if (appliedCoupon && discount > 0 && cart.length > 0) {
        discountRows.forEach(r => r.classList.remove("hidden"));
        discountVals.forEach(v => v.innerText = `-₹${discount.toFixed(2)}`);
        couponBadges.forEach(b => b.classList.remove("hidden"));
        couponNameEls.forEach(n => n.innerText = appliedCoupon.code);
    } else {
        discountRows.forEach(r => r.classList.add("hidden"));
        couponBadges.forEach(b => b.classList.add("hidden"));
    }

    const walletRows = document.querySelectorAll("#cart-wallet-row");
    const walletVals = document.querySelectorAll("#cart-wallet-val");
    const walletDeductionInfos = document.querySelectorAll("#wallet-deduction-info");
    const walletDeductionAmountEls = document.querySelectorAll("#wallet-deduction-amount");

    if (walletDeductedAmount > 0 && cart.length > 0) {
        walletRows.forEach(r => r.classList.remove("hidden"));
        walletVals.forEach(v => v.innerText = `-₹${walletDeductedAmount.toFixed(2)}`);
        walletDeductionInfos.forEach(i => i.classList.remove("hidden"));
        walletDeductionAmountEls.forEach(a => a.innerText = `-₹${walletDeductedAmount.toFixed(2)}`);
    } else {
        walletRows.forEach(r => r.classList.add("hidden"));
        walletDeductionInfos.forEach(i => i.classList.add("hidden"));
    }

    const checkoutBtns = document.querySelectorAll("#checkout-btn");
    checkoutBtns.forEach(btn => {
        btn.disabled = (cart.length === 0);
    });

    // 3. Render Drawer List
    renderCartDrawerList();

    // 4. Render Standalone /cart Page List
    renderCartPage();
}

// Render slide-over drawer items
function renderCartDrawerList() {
    const cartList = document.getElementById("cart-items-list");
    if (!cartList) return;

    if (cart.length === 0) {
        cartList.innerHTML = `
            <div class="flex flex-col items-center justify-center py-12 text-gray-400">
                <span class="text-4xl mb-2">🧺</span>
                <p class="font-medium text-gray-700">Your basket is empty</p>
                <p class="text-xs text-gray-400 mt-0.5">Explore 20 fresh Indian vegetables!</p>
            </div>
        `;
    } else {
        let html = "";
        cart.forEach(item => {
            const itemTotal = item.price * item.quantity;
            html += `
                <div class="flex items-center justify-between border-b border-gray-100 py-3">
                    <div class="flex items-center space-x-3">
                        <div class="w-11 h-11 rounded-xl bg-gray-50 border border-gray-100 flex items-center justify-center text-2xl flex-shrink-0">
                            ${item.image || '🥬'}
                        </div>
                        <div>
                            <h4 class="font-bold text-xs sm:text-sm text-gray-900 leading-tight">${item.name}</h4>
                            <p class="text-[11px] text-gray-400 font-semibold mt-0.5">${item.unit} • ₹${item.price.toFixed(2)}</p>
                        </div>
                    </div>
                    <div class="flex items-center space-x-3">
                        <div class="flex items-center bg-emerald-600 text-white rounded-xl shadow-sm overflow-hidden select-none">
                            <button onclick="addToCartRealtime(${item.id}, -1)" class="px-2 py-1 hover:bg-emerald-700 font-extrabold text-xs transition active:scale-90">-</button>
                            <span class="px-2 font-extrabold text-xs min-w-[16px] text-center">${item.quantity}</span>
                            <button onclick="addToCartRealtime(${item.id}, 1)" class="px-2 py-1 hover:bg-emerald-700 font-extrabold text-xs transition active:scale-90">+</button>
                        </div>
                        <span class="text-xs sm:text-sm font-extrabold text-gray-900 w-14 text-right">₹${itemTotal.toFixed(2)}</span>
                    </div>
                </div>
            `;
        });
        cartList.innerHTML = html;
    }
}

// Render Standalone Dedicated /cart Page View
function renderCartPage() {
    const pageContainer = document.getElementById("cart-page-items-list");
    const emptyNotice = document.getElementById("cart-page-empty");
    const itemsCard = document.getElementById("cart-page-items-container");
    const headerCount = document.getElementById("cart-header-count");
    if (!pageContainer) return;

    const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
    if (headerCount) headerCount.innerText = `${totalItems} Item${totalItems === 1 ? '' : 's'}`;

    if (cart.length === 0) {
        if (emptyNotice) emptyNotice.classList.remove("hidden");
        if (itemsCard) itemsCard.classList.add("hidden");
        return;
    }

    if (emptyNotice) emptyNotice.classList.add("hidden");
    if (itemsCard) itemsCard.classList.remove("hidden");

    let html = "";
    cart.forEach(item => {
        const itemTotal = item.price * item.quantity;
        html += `
            <div class="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-gray-50/70 transition">
                <div class="flex items-center space-x-3 sm:space-x-4">
                    <div class="w-14 h-14 rounded-2xl bg-emerald-50/80 border border-emerald-100 flex items-center justify-center text-3xl flex-shrink-0 shadow-2xs">
                        ${item.image || '🥬'}
                    </div>
                    <div>
                        <h4 class="font-black text-sm sm:text-base text-gray-900">${item.name}</h4>
                        <div class="flex items-center gap-2 mt-1">
                            <span class="text-xs font-bold text-gray-500">${item.unit}</span>
                            <span class="text-xs text-gray-300">•</span>
                            <span class="text-xs font-extrabold text-emerald-800">₹${item.price.toFixed(2)} / unit</span>
                        </div>
                    </div>
                </div>

                <div class="flex items-center justify-between sm:justify-end gap-5 pt-2 sm:pt-0 border-t sm:border-t-0 border-gray-100">
                    <!-- Quantity Stepper -->
                    <div class="flex items-center bg-emerald-600 text-white rounded-xl shadow-xs overflow-hidden select-none">
                        <button onclick="addToCartRealtime(${item.id}, -1)" class="px-3 py-1.5 hover:bg-emerald-700 font-black text-sm transition active:scale-90" title="Decrease Quantity">-</button>
                        <span class="px-3 font-black text-xs text-white min-w-[24px] text-center">${item.quantity}</span>
                        <button onclick="addToCartRealtime(${item.id}, 1)" class="px-3 py-1.5 hover:bg-emerald-700 font-black text-sm transition active:scale-90" title="Increase Quantity">+</button>
                    </div>

                    <!-- Item Total -->
                    <span class="text-base font-black text-gray-900 min-w-[70px] text-right">
                        ₹${itemTotal.toFixed(2)}
                    </span>

                    <!-- Remove Item Button -->
                    <button onclick="removeCartItem(${item.id})" class="text-gray-400 hover:text-red-600 p-2 rounded-xl hover:bg-red-50 transition" title="Remove produce item">
                        <i class="fa-solid fa-trash-can text-sm"></i>
                    </button>
                </div>
            </div>
        `;
    });
    pageContainer.innerHTML = html;
}

// Remove item completely from cart
function removeCartItem(productId) {
    const idx = cart.findIndex(item => item.id === productId);
    if (idx !== -1) {
        const removed = cart.splice(idx, 1)[0];
        saveCartToLocalStorage();
        updateCartUI();
        showToast(`Removed ${removed.name} from basket`);
    }
}

// Clear all produce in cart
function clearFullCart() {
    if (confirm("Are you sure you want to clear your farm basket?")) {
        cart = [];
        saveCartToLocalStorage();
        updateCartUI();
    }
}

// ==========================================
// DELIVERY ADDRESS MANAGER & MODAL HANDLERS
// ==========================================

// Open Address Selector & Creation Modal
async function openAddressModal() {
    const modal = document.getElementById("address-modal");
    const listContainer = document.getElementById("saved-addresses-list");
    const countEl = document.getElementById("saved-addr-count");
    if (!modal) return;
    
    modal.classList.remove("hidden");
    setModalScrollLock(true);
    
    if (listContainer) {
        listContainer.innerHTML = `
            <div class="p-4 text-center text-xs text-gray-500 font-semibold">
                <i class="fa-solid fa-circle-notch fa-spin text-emerald-600 mr-1.5"></i> Loading saved addresses...
            </div>
        `;
    }
    
    try {
        const response = await fetch("/api/user/addresses");
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.addresses) {
                userAddresses = data.addresses;
                renderSavedAddressesList(data.addresses, data.default_address);
            } else {
                renderSavedAddressesFallback();
            }
        } else {
            renderSavedAddressesFallback();
        }
    } catch (e) {
        renderSavedAddressesFallback();
    }
}

function renderSavedAddressesList(addresses, defaultAddr) {
    const listContainer = document.getElementById("saved-addresses-list");
    const countEl = document.getElementById("saved-addr-count");
    if (!listContainer) return;
    
    if (countEl) countEl.innerText = `${addresses.length} saved`;
    
    if (addresses.length === 0) {
        listContainer.innerHTML = `
            <div class="p-4 text-center bg-gray-50 rounded-2xl border border-gray-100 text-xs text-gray-400 font-medium">
                No saved addresses found. Fill in your details below to add your first delivery location!
            </div>
        `;
        return;
    }
    
    const currentAddrText = document.getElementById("delivery-address") ? document.getElementById("delivery-address").value.trim() : "";
    let html = "";
    
    addresses.forEach(addr => {
        const isSelected = (currentAddrText === addr.address || (!currentAddrText && addr.is_default));
        const icon = addr.label === 'Office' ? '🏢' : (addr.label === 'Work' ? '🏢' : '🏠');
        
        html += `
            <div class="p-3.5 rounded-2xl border ${isSelected ? 'border-emerald-500 bg-emerald-50/50 shadow-2xs' : 'border-gray-200 bg-white hover:border-gray-300'} transition flex flex-col gap-2">
                <div class="flex items-start justify-between">
                    <div class="flex items-center gap-2">
                        <span class="text-base">${icon}</span>
                        <span class="text-xs font-black text-gray-900 uppercase tracking-wide">${addr.label}</span>
                        ${addr.is_default ? '<span class="text-[9px] font-black bg-emerald-600 text-white px-2 py-0.5 rounded-md uppercase">Default</span>' : ''}
                    <div class="flex items-center gap-2">
                        ${!addr.is_default ? `
                            <button type="button" onclick="setDefaultAddress(${addr.id})" class="text-[10px] font-bold text-gray-400 hover:text-emerald-700 underline">
                                Set as Default
                            </button>
                        ` : ''}
                        <button type="button" onclick="deleteSavedAddress(${addr.id})" class="p-1 text-gray-300 hover:text-red-500 rounded transition" title="Delete Address">
                            <i class="fa-solid fa-trash-can text-xs"></i>
                        </button>
                    </div>
                </div>
                <p class="text-xs text-gray-700 font-medium leading-relaxed">${addr.address}</p>
                <div class="pt-1 flex justify-end">
                    <button type="button" onclick="selectSavedAddress(${addr.id}, '${escapeHtml(addr.address)}', '${addr.label}', ${addr.is_default ? 'true' : 'false'})" 
                            class="px-3 py-1.5 rounded-xl text-xs font-extrabold ${isSelected ? 'bg-emerald-600 text-white' : 'bg-gray-100 hover:bg-emerald-600 hover:text-white text-gray-700'} transition active:scale-95 flex items-center gap-1.5">
                        <i class="fa-solid ${isSelected ? 'fa-check' : 'fa-location-dot'} text-[10px]"></i>
                        <span>${isSelected ? 'Selected for Delivery' : 'Deliver Here'}</span>
                    </button>
                </div>
            </div>
        `;
    });
    
    listContainer.innerHTML = html;
}

function renderSavedAddressesFallback() {
    const listContainer = document.getElementById("saved-addresses-list");
    const savedAddress = localStorage.getItem("vof_customer_address") || "";
    if (!listContainer) return;
    
    if (savedAddress) {
        listContainer.innerHTML = `
            <div class="p-3.5 rounded-2xl border border-emerald-500 bg-emerald-50/50 flex flex-col gap-2">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-black text-gray-900 uppercase">🏠 Home (Saved)</span>
                    <span class="text-[9px] font-black bg-emerald-600 text-white px-2 py-0.5 rounded-md uppercase">Default</span>
                </div>
                <p class="text-xs text-gray-700 font-medium">${savedAddress}</p>
                <div class="pt-1 flex justify-end">
                    <button type="button" onclick="selectSavedAddress(0, '${escapeHtml(savedAddress)}', 'Home', true)" class="px-3 py-1.5 rounded-xl text-xs font-extrabold bg-emerald-600 text-white transition active:scale-95">
                        Selected for Delivery
                    </button>
                </div>
            </div>
        `;
    } else {
        listContainer.innerHTML = `
            <div class="p-4 text-center bg-gray-50 rounded-2xl border border-gray-100 text-xs text-gray-400 font-medium">
                Please enter your delivery flat/house address below!
            </div>
        `;
    }
}

function closeAddressModal() {
    const modal = document.getElementById("address-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

function openNewAddressModal() {
    const modal = document.getElementById("new-address-modal");
    if (modal) {
        modal.classList.remove("hidden");
        setModalScrollLock(true);
    }
}

function closeNewAddressModal() {
    const modal = document.getElementById("new-address-modal");
    if (modal) {
        modal.classList.add("hidden");
        setModalScrollLock(false);
    }
}

function selectSavedAddress(id, addrText, label, isDefault) {
    const addressInput = document.getElementById("delivery-address");
    const labelEl = document.getElementById("cart-selected-address-label");
    const textEl = document.getElementById("cart-selected-address-text");
    
    if (addressInput) addressInput.value = addrText;
    if (labelEl) labelEl.innerText = `${label} ${isDefault ? '(Default)' : ''}`;
    if (textEl) textEl.innerText = addrText;
    
    localStorage.setItem("vof_customer_address", addrText);
    closeAddressModal();
    closeNewAddressModal();
    showToast(`Delivery destination set to: ${label}`, "success");
}

async function setDefaultAddress(addrId) {
    try {
        const response = await fetch("/api/user/set-default-address", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ address_id: addrId })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            openAddressModal(); // Refresh modal
            initDeliveryAddress(); // Refresh cart preview
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error setting default address", "error");
    }
}

async function deleteSavedAddress(addrId) {
    if (!confirm("Are you sure you want to remove this delivery address?")) return;
    try {
        const response = await fetch(`/api/user/delete-address/${addrId}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            openAddressModal(); // Refresh modal
            initDeliveryAddress(); // Refresh cart preview
        } else {
            showToast(result.error || "Failed to remove address", "error");
        }
    } catch (e) {
        showToast("Error removing address", "error");
    }
}

async function handleSaveNewAddress(event) {
    if (event) event.preventDefault();
    const textEl = document.getElementById("new-addr-text") || document.getElementById("modal-new-address-input");
    const labelRadio = document.querySelector('input[name="addr_label"]:checked') || document.querySelector('input[name="new_addr_label"]:checked');
    const defaultCheck = document.getElementById("new-addr-default") || document.getElementById("modal-save-as-default");
    
    if (!textEl) return;
    const address = textEl.value.trim();
    const label = labelRadio ? labelRadio.value : "Home";
    const isDefault = defaultCheck ? defaultCheck.checked : true;
    
    if (!address) {
        showToast("Please enter complete delivery address", "error");
        return;
    }
    
    try {
        const response = await fetch("/api/user/save-address", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ label, address, is_default: isDefault })
        });
        const result = await response.json();
        if (result.success) {
            showToast("New delivery address saved!", "success");
            selectSavedAddress(result.address_id, address, label, isDefault);
            textEl.value = "";
            closeNewAddressModal();
        } else {
            selectSavedAddress(0, address, label, isDefault);
            textEl.value = "";
            closeNewAddressModal();
        }
    } catch (e) {
        selectSavedAddress(0, address, label, isDefault);
        textEl.value = "";
        closeNewAddressModal();
    }
}

function handleAddNewAddress(event) {
    return handleSaveNewAddress(event);
}

function escapeHtml(str) {
    return (str || '').replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

// ==========================================
// PROMO COUPON CODE MANAGEMENT
// ==========================================

async function applyPromoCoupon() {
    const input = document.getElementById("coupon-input");
    const msgEl = document.getElementById("coupon-message");
    const applyBtn = document.getElementById("apply-coupon-btn");
    const removeBtn = document.getElementById("remove-coupon-btn");
    const couponNameEl = document.getElementById("applied-coupon-name");
    
    if (!input) return;
    const code = input.value.trim().toUpperCase();
    if (!code) {
        showToast("Please enter a coupon code first!", "error");
        return;
    }
    
    // Calculate current cart subtotal
    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    if (subtotal <= 0) {
        showToast("Add items to your basket before applying a coupon!", "error");
        return;
    }
    
    try {
        const response = await fetch("/api/coupon/validate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ coupon_code: code, subtotal: subtotal })
        });
        
        const result = await response.json();
        if (result.success) {
            appliedCoupon = {
                code: result.coupon_code,
                discount: result.discount
            };
            
            if (couponNameEl) couponNameEl.innerText = result.coupon_code;
            if (msgEl) {
                msgEl.innerText = result.message;
                msgEl.classList.remove("hidden");
            }
            if (applyBtn) applyBtn.classList.add("hidden");
            if (removeBtn) removeBtn.classList.remove("hidden");
            input.disabled = true;
            
            updateCartUI();
            showToast(result.message, "success");
        } else {
            if (msgEl) {
                msgEl.innerText = result.error;
                msgEl.className = "text-[10px] font-bold text-red-600 mt-1.5";
                msgEl.classList.remove("hidden");
            }
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error verifying coupon with server", "error");
    }
}

function quickApplyCoupon(code) {
    const input = document.getElementById("coupon-input");
    if (input) {
        input.value = code;
        applyPromoCoupon();
    }
}

function removePromoCoupon() {
    appliedCoupon = null;
    const input = document.getElementById("coupon-input");
    const msgEl = document.getElementById("coupon-message");
    const applyBtn = document.getElementById("apply-coupon-btn");
    const removeBtn = document.getElementById("remove-coupon-btn");
    
    if (input) {
        input.value = "";
        input.disabled = false;
    }
    if (msgEl) msgEl.classList.add("hidden");
    if (applyBtn) applyBtn.classList.remove("hidden");
    if (removeBtn) removeBtn.classList.add("hidden");
    
    updateCartUI();
    showToast("Coupon removed", "info");
}

// Checkout API Trigger - Checks address and opens payment gateway modal
function checkoutCart() {
    if (cart.length === 0) return;
    
    const finalTotalEl = document.getElementById("cart-final-total");
    const cartSubtotal = document.getElementById("cart-subtotal");
    const payableText = finalTotalEl && finalTotalEl.innerText !== "₹0.00" ? finalTotalEl.innerText : (cartSubtotal ? cartSubtotal.innerText : "₹0.00");
    
    // Validate address before opening modal
    const addressEl = document.getElementById("delivery-address");
    const deliveryAddress = addressEl ? addressEl.value.trim() : "";
    
    if (!deliveryAddress || deliveryAddress.toLowerCase().includes("loading") || deliveryAddress.toLowerCase().includes("click to set")) {
        showToast("Please enter or select your delivery address first!", "error");
        openAddressModal();
        return;
    }
    
    // Update destination preview in payment modal
    const destEl = document.getElementById("gateway-delivery-destination");
    if (destEl) destEl.innerText = deliveryAddress;
    
    // Open the payment gateway simulation modal with discounted net total
    openPaymentModal(payableText);
}

// 1-Click Recipe & Tadka Combo Pack Adder
function addRecipeBundle(bundleType) {
    const BUNDLES = {
        'tadka': [
            { id: 4, name: 'Teekhi Green Chillies (Hari Mirch) [పచ్చిమిర్చి]', price: 15.00, unit: '100g', image: '🌶️', stock: 50 },
            { id: 5, name: 'Fresh Ginger (Adrak) [అల్లం]', price: 25.00, unit: '250g', image: '🫚', stock: 40 },
            { id: 6, name: 'Desi Garlic Bulbs (Lahsun) [వెల్లుల్లి]', price: 45.00, unit: '250g', image: '🧄', stock: 45 },
            { id: 7, name: 'Fresh Coriander Leaves (Hara Dhania) [కొత్తిమీర]', price: 15.00, unit: '1 Bunch', image: '🌿', stock: 60 }
        ],
        'sambar': [
            { id: 1, name: 'Hybrid Tomatoes (Tamatar) [టమోటా]', price: 35.00, unit: '1 kg', image: '🍅', stock: 80 },
            { id: 18, name: 'Fresh Bottle Gourd (Lauki) [సొరకాయ / ఆనపకాయ]', price: 30.00, unit: '1 pc (500g)', image: '🥒', stock: 30 },
            { id: 7, name: 'Fresh Coriander Leaves (Hara Dhania) [కొత్తిమీర]', price: 15.00, unit: '1 Bunch', image: '🌿', stock: 60 }
        ],
        'greens': [
            { id: 9, name: 'Fresh Spinach (Palak) [పాలకూర]', price: 25.00, unit: '1 Bunch (250g)', image: '🥬', stock: 40 },
            { id: 10, name: 'Fresh Fenugreek Leaves (Methi) [మెంతికూర]', price: 25.00, unit: '1 Bunch (250g)', image: '🌱', stock: 35 }
        ]
    };
    
    const items = BUNDLES[bundleType];
    if (!items) return;
    
    items.forEach(prod => {
        const existingIndex = cart.findIndex(i => i.id === prod.id);
        if (existingIndex !== -1) {
            cart[existingIndex].quantity += 1;
        } else {
            cart.push({ ...prod, quantity: 1 });
        }
    });
    
    saveCartToLocalStorage();
    updateCartUI();
    showToast(`Added ${bundleType.toUpperCase()} combo pack to your basket! 🎉`, "success");
}

// Actual checkout processing called after payment simulation success
async function executeSecureCheckout() {
    if (cart.length === 0) return;
    
    const items = cart.map(item => ({
        product_id: item.id,
        quantity: item.quantity
    }));
    
    const deliveryDateEl = document.getElementById("delivery-date");
    const deliverySlotEl = document.getElementById("delivery-slot");
    const addressEl = document.getElementById("delivery-address");
    
    const deliveryDate = deliveryDateEl ? deliveryDateEl.value : "";
    const deliverySlot = deliverySlotEl ? deliverySlotEl.value : "";
    const deliveryAddress = addressEl ? addressEl.value.trim() : "";
    
    if (!deliveryAddress) {
        showToast("Please select or enter a delivery address first!", "error");
        closePaymentModal();
        openAddressModal();
        return;
    }
    
    if (deliveryDate === "") {
        showToast("Please pick a valid delivery date first!", "error");
        closePaymentModal();
        return;
    }
    
    try {
        const response = await fetch("/api/checkout", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ 
                items: items,
                delivery_date: deliveryDate,
                delivery_slot: deliverySlot,
                delivery_address: deliveryAddress,
                save_as_default: true,
                coupon_code: appliedCoupon ? appliedCoupon.code : "",
                discount_amount: appliedCoupon ? appliedCoupon.discount : 0.0,
                redeem_wallet: isWalletApplied,
                wallet_redeem_amount: walletDeductedAmount
            })
        });
        
        const result = await response.json();
        
        // Hide loader in gateway modal
        closePaymentModal();
        
        if (result.success) {
            let successMsg = `Order #${result.order_id} placed successfully!`;
            if (result.cashback_earned && result.cashback_earned > 0) {
                successMsg += ` Earned ₹${result.cashback_earned.toFixed(2)} Farm Cashback coins! 🪙`;
            }
            showToast(successMsg, "success");

            cart = [];
            appliedCoupon = null;
            isWalletApplied = false;
            walletDeductedAmount = 0.0;
            const toggle = document.getElementById("use-wallet-toggle");
            if (toggle) toggle.checked = false;

            saveCartToLocalStorage(false);
            fetch("/api/cart/clear", { method: "POST" }).catch(() => {});
            updateCartUI();
            
            // Toggle cart drawer closed if open
            const drawer = document.getElementById("cart-drawer");
            if (drawer) drawer.classList.add("translate-x-full");
            
            // Open Celebratory Thank You & Delivery Assurance Popup
            openOrderSuccessModal(result, deliverySlot, deliveryAddress);
        } else {
            showToast(result.error || "Checkout failed", "error");
        }
    } catch (err) {
        closePaymentModal();
        showToast("Error establishing connection to payment backend", "error");
        console.error(err);
    }
}

// Celebratory Order Success & Thank You Modal Controllers
function openOrderSuccessModal(result, deliverySlot, deliveryAddress) {
    const modal = document.getElementById("order-success-modal");
    if (!modal) {
        // Fallback for pages without the modal
        setTimeout(() => {
            window.location.href = "/dashboard#orders";
        }, 1200);
        return;
    }
    
    const orderIdEl = document.getElementById("success-modal-order-id");
    const slotEl = document.getElementById("success-modal-slot");
    const addrEl = document.getElementById("success-modal-address");
    const cashbackRow = document.getElementById("success-modal-cashback-row");
    const cashbackVal = document.getElementById("success-modal-cashback-val");
    
    if (orderIdEl) orderIdEl.innerText = `#${result.order_id || 'VOF-ORDER'}`;
    if (slotEl) slotEl.innerText = deliverySlot || "Tomorrow • Standard Morning Slot (8:00 AM - 11:00 AM)";
    if (addrEl) addrEl.innerText = deliveryAddress || "Saved Delivery Address";
    
    const waBtn = document.getElementById("success-modal-whatsapp-btn");
    if (waBtn && result.order_id) {
        const msg = encodeURIComponent(`Hello PPM Organic Farms, I have an inquiry about my recent Order #${result.order_id}!`);
        waBtn.href = `https://wa.me/917675960440?text=${msg}`;
    }
    
    if (cashbackRow && cashbackVal) {
        if (result.cashback_earned && result.cashback_earned > 0) {
            cashbackVal.innerText = `+₹${result.cashback_earned.toFixed(2)} Farm Cashback`;
            cashbackRow.classList.remove("hidden");
        } else {
            cashbackRow.classList.add("hidden");
        }
    }
    
    modal.classList.remove("hidden");
    setModalScrollLock(true);
    
    // Play celebratory order chime if audio enabled
    try {
        playOrderNotificationChime();
    } catch(e) {}
}

function closeOrderSuccessModal(targetTab = 'orders') {
    const modal = document.getElementById("order-success-modal");
    if (modal) {
        modal.classList.add("hidden");
        setModalScrollLock(false);
    }
    // Always navigate to fresh dashboard with target tab to guarantee newly placed orders appear immediately in history
    window.location.href = `/dashboard?tab=${targetTab}`;
}

// Admin: Update Order Status API (Placed -> Packed at Farm -> Out for Delivery -> Delivered)
async function updateOrderStatusAdmin(orderId, newStatus) {
    try {
        const response = await fetch("/api/admin/order-status", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ order_id: orderId, status: newStatus })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error updating order status", "error");
    }
}

// =========================================================================
// COMMERCIAL ADMIN WORKFLOW & SLIDE-OVER ORDER DRAWER CONTROLLERS
// =========================================================================

// Open Slide-Over Drawer with Complete Customer Profile & Harvest Manifest
async function openAdminOrderDrawer(orderId) {
    const drawer = document.getElementById("admin-order-drawer");
    const backdrop = document.getElementById("admin-order-drawer-backdrop");
    const container = document.getElementById("admin-order-drawer-content");
    if (!drawer || !container) return;

    if (backdrop) {
        backdrop.classList.remove("hidden");
        backdrop.style.display = "block";
    }
    drawer.classList.remove("hidden");
    drawer.style.display = "flex";
    requestAnimationFrame(() => {
        drawer.classList.remove("translate-x-full");
    });
    setModalScrollLock(true);

    container.innerHTML = `
        <div class="py-20 text-center text-gray-400 space-y-3">
            <i class="fa-solid fa-circle-notch fa-spin text-3xl text-emerald-600"></i>
            <p class="text-xs font-bold text-gray-600">Loading full order details & harvest manifest for #${orderId}...</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/admin/order-details/${orderId}`);
        const data = await response.json();
        if (!data.success) {
            container.innerHTML = `<div class="p-6 text-center text-red-600 font-bold">${data.error || 'Failed to load order'}</div>`;
            return;
        }

        const { customer, order, items } = data;

        const statusColors = {
            'Placed': 'bg-indigo-50 text-indigo-800 border-indigo-200',
            'Packed at Farm': 'bg-blue-50 text-blue-800 border-blue-200',
            'Out for Delivery': 'bg-amber-50 text-amber-800 border-amber-200',
            'Delivered': 'bg-emerald-50 text-emerald-800 border-emerald-200',
            'Cancelled': 'bg-red-50 text-red-800 border-red-200'
        };
        const statusClass = statusColors[order.status] || 'bg-gray-100 text-gray-800 border-gray-200';

        let itemsHtml = items.map(item => `
            <tr class="border-b border-gray-100 text-xs hover:bg-gray-50/50 transition">
                <td class="py-3 pr-2">
                    <div class="flex items-center space-x-2.5">
                        <span class="text-2xl flex-shrink-0">${item.image || '🥬'}</span>
                        <div>
                            <p class="font-extrabold text-gray-900 leading-tight">${item.name}</p>
                            <span class="text-[10px] text-gray-400 font-semibold uppercase">${item.category || 'Produce'}</span>
                        </div>
                    </div>
                </td>
                <td class="py-3 text-center text-gray-600 font-bold">${item.unit || '1 unit'}</td>
                <td class="py-3 text-center font-black text-gray-900 bg-emerald-50/60 rounded-lg">${item.quantity}</td>
                <td class="py-3 text-right text-gray-600 font-medium">₹${item.price.toFixed(2)}</td>
                <td class="py-3 text-right font-black text-gray-900">₹${item.total_price.toFixed(2)}</td>
            </tr>
        `).join('');

        let actionButtonsHtml = '';
        if (order.status === 'Placed') {
            actionButtonsHtml = `
                <div class="space-y-2">
                    <button type="button" onclick="submitAdminOrderAction('${order.order_id}', 'accept')"
                            class="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-black py-3.5 px-4 rounded-2xl shadow-lg shadow-emerald-600/25 text-xs transition active:scale-98 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-box-open"></i>
                        <span>1. Accept Order & Pack at Farm</span>
                    </button>
                    <button type="button" onclick="submitAdminOrderAction('${order.order_id}', 'cancel')"
                            class="w-full bg-red-50 hover:bg-red-100 text-red-700 font-extrabold py-2.5 px-4 rounded-xl border border-red-200 text-xs transition active:scale-98">
                        Cancel Order
                    </button>
                </div>
            `;
        } else if (order.status === 'Packed at Farm') {
            actionButtonsHtml = `
                <div class="space-y-2">
                    <button type="button" onclick="submitAdminOrderAction('${order.order_id}', 'dispatch')"
                            class="w-full bg-amber-500 hover:bg-amber-600 text-white font-black py-3.5 px-4 rounded-2xl shadow-lg shadow-amber-500/25 text-xs transition active:scale-98 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-truck-fast"></i>
                        <span>2. Dispatch Order (Out for Delivery)</span>
                    </button>
                </div>
            `;
        } else if (order.status === 'Out for Delivery') {
            actionButtonsHtml = `
                <div class="space-y-2">
                    <button type="button" onclick="submitAdminOrderAction('${order.order_id}', 'deliver')"
                            class="w-full bg-emerald-700 hover:bg-emerald-800 text-white font-black py-3.5 px-4 rounded-2xl shadow-lg shadow-emerald-700/25 text-xs transition active:scale-98 flex items-center justify-center gap-2">
                        <i class="fa-solid fa-circle-check"></i>
                        <span>3. Mark Order as Delivered</span>
                    </button>
                </div>
            `;
        } else if (order.status === 'Delivered') {
            actionButtonsHtml = `
                <div class="w-full bg-emerald-50 text-emerald-800 border border-emerald-200 py-3 rounded-2xl text-center text-xs font-black flex items-center justify-center gap-2">
                    <i class="fa-solid fa-circle-check text-emerald-600"></i>
                    <span>Harvest Delivered Successfully</span>
                </div>
            `;
        } else {
            actionButtonsHtml = `
                <div class="w-full bg-red-50 text-red-800 border border-red-200 py-3 rounded-2xl text-center text-xs font-black">
                    Order Cancelled
                </div>
            `;
        }

        container.innerHTML = `
            <!-- Top Summary Header -->
            <div class="p-6 border-b border-gray-100 bg-gray-50/70 space-y-3">
                <div class="flex items-center justify-between">
                    <div>
                        <span class="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">Harvest Order Reference</span>
                        <span class="font-mono text-lg font-black text-gray-900">#${order.order_id}</span>
                    </div>
                    <span class="text-xs font-black px-3 py-1.5 rounded-xl border ${statusClass}">
                        ${order.status}
                    </span>
                </div>
                <div class="text-[11px] text-gray-500 flex items-center gap-1.5">
                    <i class="fa-solid fa-calendar-check text-emerald-600"></i>
                    <span>Placed on: <strong>${order.purchase_date}</strong></span>
                </div>
            </div>

            <div class="p-6 space-y-6 flex-grow overflow-y-auto">
                <!-- 1. Customer Profile -->
                <div class="space-y-2">
                    <h4 class="text-xs font-black text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                        <i class="fa-solid fa-user text-emerald-600"></i> Customer Profile & CRM
                    </h4>
                    <div class="bg-gray-50 p-4 rounded-2xl border border-gray-100 space-y-2.5 text-xs">
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-gray-500">Full Name:</span>
                            <span class="font-black text-gray-900">${customer.name} (Buyer #${customer.id})</span>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-gray-500">Contact Number:</span>
                            <div class="flex items-center gap-2">
                                <a href="tel:${customer.phone}" class="font-extrabold text-emerald-700 hover:underline">
                                    📞 +91 ${customer.phone}
                                </a>
                                <a href="https://wa.me/91${customer.phone.replace(/[^0-9]/g, '')}" target="_blank" class="text-emerald-600 hover:text-emerald-700 text-sm" title="Message Customer on WhatsApp">
                                    <i class="fa-brands fa-whatsapp"></i>
                                </a>
                            </div>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="font-bold text-gray-500">Email:</span>
                            <span class="font-semibold text-gray-700">${customer.email}</span>
                        </div>
                        <div class="flex items-center justify-between pt-1.5 border-t border-gray-200/70">
                            <span class="font-bold text-gray-500">Farm Wallet:</span>
                            <span class="font-black text-amber-700">🪙 ₹${customer.wallet_balance.toFixed(2)} Coins</span>
                        </div>
                        <div class="flex items-center justify-between pt-1.5 border-t border-gray-200/70">
                            <span class="font-bold text-gray-500">Order History:</span>
                            <a href="/admin/customers?customer_id=${customer.id}" class="inline-flex items-center gap-1 font-black text-purple-700 hover:text-purple-900 bg-purple-50 hover:bg-purple-100 px-2.5 py-1 rounded-lg border border-purple-200 transition text-[11px]" title="View Customer Profile & Full Past Orders">
                                <i class="fa-solid fa-clock-rotate-left"></i>
                                <span>Inspect Customer History</span>
                            </a>
                        </div>
                    </div>
                </div>

                <!-- 2. Delivery Destination & Schedule -->
                <div class="space-y-2">
                    <div class="flex items-center justify-between">
                        <h4 class="text-xs font-black text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                            <i class="fa-solid fa-map-location-dot text-emerald-600"></i> Delivery Details
                        </h4>
                        <button type="button" onclick="promptEditOrderAddress('${order.order_id}', '${escapeHtml(order.delivery_address)}')"
                                class="text-[10px] font-black text-emerald-700 hover:text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-200 transition">
                            Edit Address
                        </button>
                    </div>
                    <div class="bg-gray-50 p-4 rounded-2xl border border-gray-100 space-y-2 text-xs">
                        <div class="flex items-center justify-between text-emerald-800 font-bold">
                            <span>📅 Harvest Schedule:</span>
                            <span class="font-black">${order.delivery_date} • ${order.delivery_slot}</span>
                        </div>
                        <div>
                            <span class="font-bold text-gray-500 block mb-1">📍 Destination Address:</span>
                            <p class="font-bold text-gray-800 leading-relaxed bg-white p-3 rounded-xl border border-gray-200/70">
                                ${order.delivery_address}
                            </p>
                        </div>
                    </div>
                </div>

                <!-- 3. Ordered Harvest Produce Breakdown -->
                <div class="space-y-2">
                    <h4 class="text-xs font-black text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                        <i class="fa-solid fa-basket-shopping text-emerald-600"></i> Ordered Harvest (${items.length} items)
                    </h4>
                    <div class="overflow-x-auto border border-gray-100 rounded-2xl">
                        <table class="min-w-full divide-y divide-gray-100">
                            <thead class="bg-gray-50 text-[10px] font-extrabold text-gray-400 uppercase">
                                <tr>
                                    <th class="py-2.5 pl-3 text-left">Produce</th>
                                    <th class="py-2.5 text-center">Unit</th>
                                    <th class="py-2.5 text-center">Qty</th>
                                    <th class="py-2.5 text-right">Price</th>
                                    <th class="py-2.5 pr-3 text-right">Subtotal</th>
                                </tr>
                            </thead>
                            <tbody class="divide-y divide-gray-100 bg-white">
                                ${itemsHtml}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- 4. Pricing & Tax Breakdown -->
                <div class="bg-gray-50 p-4 rounded-2xl border border-gray-100 space-y-2 text-xs">
                    <div class="flex justify-between text-gray-600 font-bold">
                        <span>Harvest Items Subtotal</span>
                        <span>₹${order.subtotal.toFixed(2)}</span>
                    </div>
                    ${order.discount_amount > 0 ? `
                        <div class="flex justify-between text-emerald-600 font-black">
                            <span>Coupon Discount (${order.coupon_code || 'APPLIED'})</span>
                            <span>-₹${order.discount_amount.toFixed(2)}</span>
                        </div>
                    ` : ''}
                    <div class="flex justify-between text-gray-500 font-bold">
                        <span>Express Delivery Fee</span>
                        <span class="text-emerald-700 font-black">FREE (₹0.00)</span>
                    </div>
                    <div class="flex justify-between text-sm font-black text-gray-900 pt-2 border-t border-gray-200">
                        <span>Order Total (Net Payable)</span>
                        <span class="text-base text-emerald-800">₹${order.order_total.toFixed(2)}</span>
                    </div>
                </div>
            </div>

            <!-- Sticky Bottom Dispatch Actions -->
            <div class="p-6 border-t border-gray-100 bg-white space-y-2.5">
                ${actionButtonsHtml}
                <button type="button" onclick="openInvoiceModal('${order.order_id}')"
                        class="w-full bg-gray-100 hover:bg-gray-200 text-gray-800 font-bold py-3 rounded-xl text-xs transition flex items-center justify-center gap-1.5 active:scale-98">
                    <i class="fa-solid fa-file-invoice text-emerald-600"></i>
                    <span>View / Print Customer Tax Invoice</span>
                </button>
            </div>
        `;
    } catch (err) {
        container.innerHTML = `<div class="p-6 text-center text-red-600 font-bold">Error connecting to server.</div>`;
        console.error(err);
    }
}

function closeAdminOrderDrawer() {
    const drawer = document.getElementById("admin-order-drawer");
    const backdrop = document.getElementById("admin-order-drawer-backdrop");
    if (drawer) {
        drawer.classList.add("translate-x-full");
        setTimeout(() => {
            drawer.classList.add("hidden");
            drawer.style.display = "none";
        }, 300);
    }
    if (backdrop) {
        backdrop.classList.add("hidden");
        backdrop.style.display = "none";
    }
    setModalScrollLock(false);
}

async function submitAdminOrderAction(orderId, action, extraData = {}) {
    try {
        const response = await fetch("/api/admin/order-action", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ order_id: orderId, action: action, ...extraData })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            openAdminOrderDrawer(orderId);
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(result.error || "Action failed", "error");
        }
    } catch (e) {
        showToast("Error communicating with admin server", "error");
    }
}

function promptEditOrderAddress(orderId, currentAddr) {
    const newAddr = prompt(`Update Delivery Address for #${orderId}:`, currentAddr);
    if (newAddr && newAddr.trim() !== "" && newAddr.trim() !== currentAddr) {
        submitAdminOrderAction(orderId, 'update_address', { delivery_address: newAddr.trim() });
    }
}

// Admin: Delete Vegetable
async function deleteProductAdmin(productId, productName) {
    if (!confirm(`Are you sure you want to permanently delete '${productName}' from the produce catalog?`)) {
        return;
    }
    try {
        const response = await fetch(`/api/admin/delete-product/${productId}`, {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast(result.error || "Delete failed", "error");
        }
    } catch (e) {
        showToast("Error communicating with server", "error");
    }
}

// Admin: Open Create Vegetable Modal
function openAddProductModal() {
    const modal = document.getElementById("admin-add-product-modal");
    if (modal) {
        modal.classList.remove("hidden");
        setModalScrollLock(true);
    }
}

function closeAddProductModal() {
    const modal = document.getElementById("admin-add-product-modal");
    if (modal) {
        modal.classList.add("hidden");
        setModalScrollLock(false);
    }
}

// Admin: Submit New Vegetable
async function submitAddProduct(e) {
    e.preventDefault();
    const name = document.getElementById("create-prod-name").value.trim();
    const category = document.getElementById("create-prod-category").value;
    const price = parseFloat(document.getElementById("create-prod-price").value);
    const unit = document.getElementById("create-prod-unit").value.trim();
    const stock = parseInt(document.getElementById("create-prod-stock").value);
    const image_url = document.getElementById("create-prod-image").value.trim() || "🥬";
    const tags = document.getElementById("create-prod-tags").value.trim();
    const description = document.getElementById("create-prod-desc").value.trim();

    try {
        const response = await fetch("/api/admin/create-product", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name, category, price, unit, stock, image_url, tags, description })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            closeAddProductModal();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(result.error || "Failed to create product", "error");
        }
    } catch (err) {
        showToast("Error creating product", "error");
    }
}

// Admin: Customer Wallet Modal
function openCustomerWalletModal(userId, customerName, currentBalance) {
    const modal = document.getElementById("customer-wallet-modal");
    if (!modal) return;

    document.getElementById("wallet-modal-uid").value = userId;
    document.getElementById("wallet-modal-cust-name").innerText = customerName;
    document.getElementById("wallet-modal-cur-balance").innerText = `₹${parseFloat(currentBalance).toFixed(2)}`;
    document.getElementById("wallet-modal-amount").value = "";
    document.getElementById("wallet-modal-reason").value = "";

    modal.classList.remove("hidden");
    setModalScrollLock(true);
}

function closeCustomerWalletModal() {
    const modal = document.getElementById("customer-wallet-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

async function submitCustomerWalletAdjustment(e) {
    e.preventDefault();
    const uid = parseInt(document.getElementById("wallet-modal-uid").value);
    const amount = parseFloat(document.getElementById("wallet-modal-amount").value);
    const txType = document.querySelector('input[name="wallet_tx_type"]:checked').value;
    const reason = document.getElementById("wallet-modal-reason").value.trim();

    if (isNaN(amount) || amount <= 0) {
        showToast("Please enter a valid coins amount", "error");
        return;
    }

    try {
        const response = await fetch("/api/admin/customer/update-wallet", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: uid, amount, type: txType, reason })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            closeCustomerWalletModal();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(result.error || "Wallet update failed", "error");
        }
    } catch (err) {
        showToast("Error communicating with server", "error");
    }
}

// Admin: Toggle Customer Role
async function toggleCustomerRole(userId, currentRole) {
    const newRole = currentRole === 'admin' ? 'customer' : 'admin';
    if (!confirm(`Are you sure you want to change this user's role to '${newRole}'?`)) return;

    try {
        const response = await fetch("/api/admin/customer/update-role", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ user_id: userId, role: newRole })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast(result.error || "Role update failed", "error");
        }
    } catch (e) {
        showToast("Error updating user role", "error");
    }
}

// Admin: Delete Customer Account
async function deleteCustomerAdmin(userId, name) {
    if (!confirm(`Are you sure you want to permanently delete customer '${name}' and all associated purchase records?`)) return;

    try {
        const response = await fetch(`/api/admin/customer/delete/${userId}`, {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast(result.error || "Delete failed", "error");
        }
    } catch (e) {
        showToast("Error deleting customer account", "error");
    }
}

// Admin: Add Promo Coupon
function openAddCouponModal() {
    const modal = document.getElementById("admin-add-coupon-modal");
    if (modal) {
        modal.classList.remove("hidden");
        setModalScrollLock(true);
    }
}

function closeAddCouponModal() {
    const modal = document.getElementById("admin-add-coupon-modal");
    if (modal) {
        modal.classList.add("hidden");
        setModalScrollLock(false);
    }
}

async function submitCreateCoupon(e) {
    e.preventDefault();
    const code = document.getElementById("new-coupon-code").value.trim().toUpperCase();
    const type = document.getElementById("new-coupon-type").value;
    const value = parseFloat(document.getElementById("new-coupon-value").value);
    const min_order = parseFloat(document.getElementById("new-coupon-min-order").value) || 0.0;
    const max_discount = parseFloat(document.getElementById("new-coupon-max-disc").value) || value;
    const description = document.getElementById("new-coupon-desc").value.trim();

    try {
        const response = await fetch("/api/admin/coupon/create", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ code, type, value, min_order, max_discount, description })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            closeAddCouponModal();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(result.error || "Failed to create coupon", "error");
        }
    } catch (err) {
        showToast("Error creating coupon", "error");
    }
}

// Admin: Delete Promo Coupon
async function deleteCouponAdmin(couponId, code) {
    if (!confirm(`Are you sure you want to deactivate and remove coupon '${code}'?`)) return;

    try {
        const response = await fetch(`/api/admin/coupon/delete/${couponId}`, {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => window.location.reload(), 800);
        } else {
            showToast(result.error || "Delete failed", "error");
        }
    } catch (e) {
        showToast("Error deleting coupon", "error");
    }
}

// Fetch and Open Itemized Invoice / Receipt Modal
async function openInvoiceModal(orderId) {
    const modal = document.getElementById("invoice-modal");
    const container = document.getElementById("invoice-modal-content");
    if (!modal || !container) return;
    
    modal.classList.remove("hidden");
    setModalScrollLock(true);
    container.innerHTML = `
        <div class="p-8 text-center text-gray-500">
            <i class="fa-solid fa-circle-notch fa-spin text-2xl text-emerald-600 mb-2"></i>
            <p class="font-bold text-xs">Generating official bill for #${orderId}...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/order/invoice/${orderId}`);
        const result = await response.json();
        if (!result.success) {
            container.innerHTML = `<p class="text-red-500 font-bold p-6 text-center">${result.error}</p>`;
            return;
        }
        
        const inv = result.invoice;
        let itemsHtml = "";
        inv.items.forEach(item => {
            itemsHtml += `
                <tr class="border-b border-gray-100">
                    <td class="py-2.5 text-xs font-bold text-gray-900 flex items-center gap-2">
                        <span>${item.icon || '🥬'}</span>
                        <span>${item.name}</span>
                    </td>
                    <td class="py-2.5 text-xs text-center text-gray-500 font-medium">${item.unit}</td>
                    <td class="py-2.5 text-xs text-center font-bold text-gray-900">${item.quantity}</td>
                    <td class="py-2.5 text-xs text-right font-bold text-gray-700">₹${item.price.toFixed(2)}</td>
                    <td class="py-2.5 text-xs text-right font-black text-gray-900">₹${item.total.toFixed(2)}</td>
                </tr>
            `;
        });
        
        container.innerHTML = `
            <div class="p-6 bg-white space-y-5" id="printable-invoice-sheet">
                <!-- Invoice Header -->
                <div class="flex items-start justify-between border-b pb-4 border-gray-100">
                    <div class="flex items-center space-x-3">
                        <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-600 to-green-500 flex items-center justify-center text-white">
                            <i class="fa-solid fa-leaf text-lg"></i>
                        </div>
                        <div>
                            <h3 class="font-black text-base text-gray-900">PPM ORGANIC FARMS</h3>
                            <p class="text-[10px] font-bold text-emerald-700">100% Certified Organic • Direct Harvest</p>
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="inline-block bg-emerald-100 text-emerald-900 text-[10px] font-extrabold px-2.5 py-0.5 rounded-full uppercase">
                            ${inv.status}
                        </span>
                        <p class="text-xs font-black text-gray-900 mt-1 font-mono">${inv.order_id}</p>
                        <p class="text-[10px] text-gray-400 font-semibold">${inv.purchase_date}</p>
                    </div>
                </div>

                <!-- Customer & Delivery Meta -->
                <div class="grid grid-cols-2 gap-4 bg-gray-50/70 p-3.5 rounded-2xl text-xs border border-gray-100">
                    <div>
                        <p class="text-[9px] font-bold text-gray-400 uppercase">Customer Details</p>
                        <p class="font-bold text-gray-900 mt-0.5">${inv.customer_name}</p>
                        <p class="text-gray-500 font-medium">📞 +91 ${inv.customer_phone}</p>
                    </div>
                    <div>
                        <p class="text-[9px] font-bold text-gray-400 uppercase">Delivery Schedule & Address</p>
                        <p class="font-bold text-emerald-800 mt-0.5">📅 ${inv.delivery_date} • ${inv.delivery_slot}</p>
                        <p class="text-gray-600 text-[11px] font-medium leading-tight mt-0.5">📍 ${inv.delivery_address}</p>
                    </div>
                </div>

                <!-- Itemized Table -->
                <table class="w-full text-left">
                    <thead>
                        <tr class="border-b border-gray-200 text-[10px] font-bold text-gray-400 uppercase">
                            <th class="py-2">Item Description</th>
                            <th class="py-2 text-center">Unit</th>
                            <th class="py-2 text-center">Qty</th>
                            <th class="py-2 text-right">Price</th>
                            <th class="py-2 text-right">Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${itemsHtml}
                    </tbody>
                </table>

                <!-- Summary Footer -->
                <div class="border-t border-gray-100 pt-3 space-y-1.5 text-xs">
                    <div class="flex justify-between text-gray-500 font-medium">
                        <span>Items Subtotal</span>
                        <span class="font-bold text-gray-800">₹${inv.subtotal.toFixed(2)}</span>
                    </div>
                    ${inv.discount_amount > 0 ? `
                        <div class="flex justify-between text-emerald-600 font-bold">
                            <span>Coupon Discount (${inv.coupon_code || 'APPLIED'})</span>
                            <span>-₹${inv.discount_amount.toFixed(2)}</span>
                        </div>
                    ` : ''}
                    <div class="flex justify-between text-emerald-700 font-bold">
                        <span>Farm Fresh Delivery Fee</span>
                        <span>FREE (₹0.00)</span>
                    </div>
                    <div class="flex justify-between text-sm font-black text-gray-900 border-t pt-2 border-gray-200">
                        <span>Net Paid Amount</span>
                        <span class="text-base text-emerald-700">₹${inv.grand_total.toFixed(2)}</span>
                    </div>
                </div>
            </div>
        `;
        currentActiveInvoice = inv;
    } catch (e) {
        container.innerHTML = `<p class="text-red-500 p-6 text-center font-bold">Failed to load invoice receipt.</p>`;
    }
}

function closeInvoiceModal() {
    const modal = document.getElementById("invoice-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

function printInvoice() {
    window.print();
}

// WhatsApp Order Share Feature
function shareOrderOnWhatsApp(orderId, name, total, status, address) {
    const cleanName = (name || 'Fresh Organic Vegetables').split('[')[0].trim();
    const text = `🌿 *Vamsi Organic Farms - Order Update* 🥬\n\n` +
                 `📦 *Order ID:* #${orderId}\n` +
                 `🥦 *Produce:* ${cleanName}\n` +
                 `💰 *Total Amount:* ₹${parseFloat(total).toFixed(2)}\n` +
                 `📍 *Destination:* ${address || 'Local Delivery'}\n` +
                 `⚡ *Live Status:* ${status}\n\n` +
                 `Track order live: ${window.location.origin}/dashboard\n` +
                 `Thank you for choosing 100% pure organic harvest! 🚜✨`;
                 
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
    window.open(url, '_blank');
}

// WhatsApp Share Bill from Invoice Modal
function shareCurrentInvoiceWhatsApp() {
    if (!currentActiveInvoice) {
        showToast("Open an invoice to share receipt", "info");
        return;
    }
    const inv = currentActiveInvoice;
    let itemsText = inv.items.map(i => `• ${i.name.split('[')[0].trim()} (x${i.quantity} ${i.unit}) - ₹${i.total.toFixed(2)}`).join('\n');
    
    let discText = inv.discount_amount > 0 ? `\n🏷️ *Coupon Discount:* -₹${inv.discount_amount.toFixed(2)} (${inv.coupon_code || 'APPLIED'})` : '';
    
    const text = `🧾 *OFFICIAL BILL - VAMSI ORGANIC FARMS* 🌿\n\n` +
                 `*Order ID:* #${inv.order_id}\n` +
                 `*Customer:* ${inv.customer_name} (+91 ${inv.customer_phone})\n` +
                 `*Delivery:* ${inv.delivery_date} (${inv.delivery_slot})\n` +
                 `*Destination:* ${inv.delivery_address}\n\n` +
                 `*Items Purchased:*\n${itemsText}\n` +
                 `------------------------\n` +
                 `*Subtotal:* ₹${inv.subtotal.toFixed(2)}` +
                 discText + `\n` +
                 `*Net Paid Amount:* ₹${inv.grand_total.toFixed(2)}\n` +
                 `*Status:* ${inv.status}\n\n` +
                 `100% Certified Farm-Direct Organic Produce! 🚜✨`;
                 
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`;
    window.open(url, '_blank');
}

// Cancel Placed Order with Stock Restoration
async function confirmCancelOrder(orderId) {
    if (!confirm(`Are you sure you want to cancel Order #${orderId}?\n\nVegetable inventory will be immediately restored to the farm.`)) {
        return;
    }
    
    try {
        const response = await fetch('/api/order/cancel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            showToast(result.error || "Could not cancel order", "error");
        }
    } catch (e) {
        showToast("Error connecting to cancellation service", "error");
    }
}

// Notification Dismiss API
async function dismissNotification(nid, elementId) {
    try {
        const response = await fetch(`/api/notifications/dismiss/${nid}`, {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            const el = document.getElementById(elementId);
            if (el) {
                el.classList.add("scale-95", "opacity-0");
                setTimeout(() => {
                    el.remove();
                    // Check if there are no notification elements remaining
                    const list = document.getElementById("notifications-list");
                    if (list && list.querySelectorAll("[id^='notif-']").length === 0) {
                        list.innerHTML = `
                            <div class="py-8 text-center text-gray-400">
                                <span class="text-3xl mb-2 block">🔔</span>
                                <p class="text-sm font-semibold">You're all caught up!</p>
                                <p class="text-xs text-gray-400">Fresh updates and restocking alerts will appear here.</p>
                            </div>
                        `;
                    }
                }, 300);
            }
            // Update unread count badge in header
            window.location.reload(); // Reload is easiest to keep badge + DB in sync
        }
    } catch (e) {
        console.error("Failed to dismiss notification", e);
    }
}

// Dismiss all notifications
async function dismissAllNotifications() {
    try {
        const response = await fetch("/api/notifications/dismiss-all", {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            window.location.reload();
        }
    } catch (e) {
        console.error("Failed to dismiss all notifications", e);
    }
}

// Admin: Trigger restock API
async function restockProduct(productId) {
    const qtyInput = document.getElementById(`restock-qty-${productId}`);
    if (!qtyInput) return;
    
    const qty = parseInt(qtyInput.value) || 10;
    
    try {
        const response = await fetch("/api/admin/restock", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ product_id: productId, quantity: qty })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error communicating with server", "error");
        console.error(e);
    }
}

// Dashboard: Trigger dynamic AI restock predictions
async function runPredictiveAI() {
    try {
        const response = await fetch("/api/notifications/trigger-predictive", {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "info");
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error running AI predictor", "error");
    }
}

// Admin: Update product details (name, price, stock)
async function updateProductDetails(productId) {
    const nameInput = document.getElementById(`prod-name-${productId}`);
    const priceInput = document.getElementById(`prod-price-${productId}`);
    const stockInput = document.getElementById(`prod-stock-${productId}`);
    if (!nameInput || !priceInput || !stockInput) return;
    
    const name = nameInput.value.trim();
    const price = parseFloat(priceInput.value);
    const stock = parseInt(stockInput.value);
    
    if (name === "") {
        showToast("Product name cannot be empty", "error");
        return;
    }
    if (isNaN(price) || price < 0) {
        showToast("Please enter a valid positive price", "error");
        return;
    }
    if (isNaN(stock) || stock < 0) {
        showToast("Please enter a valid positive stock quantity", "error");
        return;
    }
    
    try {
        const response = await fetch("/api/admin/update-product", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ product_id: productId, name: name, price: price, stock: stock })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error updating product details", "error");
        console.error(e);
    }
}

// Admin: Add new vegetable product
async function addProduct() {
    const name = document.getElementById("new-name").value.trim();
    const category = document.getElementById("new-category").value;
    const price = parseFloat(document.getElementById("new-price").value);
    const unit = document.getElementById("new-unit").value.trim();
    const stock = parseInt(document.getElementById("new-stock").value);
    const image = document.getElementById("new-image").value.trim();
    const tags = document.getElementById("new-tags").value.trim();
    const description = document.getElementById("new-description").value.trim();

    if (name === "" || isNaN(price) || isNaN(stock) || unit === "" || description === "") {
        showToast("Please fill out all fields correctly", "error");
        return;
    }

    try {
        const response = await fetch("/api/admin/create-product", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                category: category,
                price: price,
                unit: unit,
                stock: stock,
                image_url: image,
                tags: tags,
                description: description
            })
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            document.getElementById("add-product-form").reset();
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error adding new product", "error");
        console.error(e);
    }
}

// Admin: Delete a product
async function deleteProduct(productId) {
    if (!confirm("Are you sure you want to permanently delete this vegetable from the catalog?")) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/delete-product/${productId}`, {
            method: "POST"
        });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, "success");
            setTimeout(() => {
                window.location.reload();
            }, 1500);
        } else {
            showToast(result.error, "error");
        }
    } catch (e) {
        showToast("Error deleting product", "error");
        console.error(e);
    }
}

// ==========================================
// REAL-TIME ADMIN ORDER NOTIFICATION & POPUP
// ==========================================
let lastSeenNotificationId = 0;
let adminPollInterval = null;
let adminAudioContext = null;
let adminAudioEnabled = true;
let titleFlashInterval = null;
const originalDocTitle = document.title;

function getAdminAudioContext() {
    if (!adminAudioContext) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) adminAudioContext = new AudioCtx();
    }
    if (adminAudioContext && adminAudioContext.state === 'suspended') {
        adminAudioContext.resume().catch(() => {});
    }
    return adminAudioContext;
}

function toggleAdminAudioAlerts() {
    adminAudioEnabled = !adminAudioEnabled;
    const btn = document.getElementById("admin-audio-toggle-btn");
    const icon = document.getElementById("admin-audio-icon");
    const text = document.getElementById("admin-audio-text");
    
    // Resume context on user click
    const ctx = getAdminAudioContext();
    if (ctx && ctx.state === 'suspended') {
        ctx.resume();
    }
    
    // Request desktop notification permission on interaction
    requestDesktopNotificationPermission();

    if (adminAudioEnabled) {
        if (icon) icon.className = "fa-solid fa-volume-high text-emerald-600";
        if (text) text.innerText = "Audio Alerts: ON";
        if (btn) btn.className = "bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-extrabold text-xs px-3.5 py-2.5 rounded-xl border border-emerald-200 shadow-xs inline-flex items-center gap-1.5 transition active:scale-95";
        playAlertChime();
        showToast("🔔 Audio alerts active. Test chime played.", "success");
    } else {
        if (icon) icon.className = "fa-solid fa-volume-xmark text-gray-400";
        if (text) text.innerText = "Audio Alerts: OFF";
        if (btn) btn.className = "bg-gray-100 hover:bg-gray-200 text-gray-600 font-extrabold text-xs px-3.5 py-2.5 rounded-xl border border-gray-200 shadow-xs inline-flex items-center gap-1.5 transition active:scale-95";
        showToast("Audio alerts muted", "info");
    }
}

function requestDesktopNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission().catch(() => {});
    }
}

function showDesktopNotification(title, body) {
    if ("Notification" in window && Notification.permission === "granted") {
        try {
            new Notification(title, {
                body: body,
                icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🥬</text></svg>"
            });
        } catch (e) {}
    }
}

function flashTitleNotification(message) {
    if (titleFlashInterval) clearInterval(titleFlashInterval);
    let state = false;
    titleFlashInterval = setInterval(() => {
        document.title = state ? `🔔 NEW ORDER! - ${originalDocTitle}` : `🛒 Incoming Farm Order!`;
        state = !state;
    }, 1000);

    const stopFlash = () => {
        clearInterval(titleFlashInterval);
        titleFlashInterval = null;
        document.title = originalDocTitle;
        window.removeEventListener("focus", stopFlash);
        window.removeEventListener("click", stopFlash);
    };
    window.addEventListener("focus", stopFlash);
    window.addEventListener("click", stopFlash);
}

function updateAdminBadges(count) {
    const navBadge = document.getElementById("nav-admin-order-badge");
    const mobileBadge = document.getElementById("mobile-admin-order-badge");
    [navBadge, mobileBadge].forEach(badge => {
        if (badge) {
            badge.innerText = count;
            if (count > 0) badge.classList.remove("hidden");
            else badge.classList.add("hidden");
        }
    });
}

let adminTableInterval = null;
function startAdminLiveOrderPolling() {
    if (adminPollInterval) clearInterval(adminPollInterval);
    // Poll every 3 seconds for instant real-time delivery alerts
    adminPollInterval = setInterval(checkAdminNewOrders, 3000);
    checkAdminNewOrders();

    if (window.location.pathname.startsWith("/admin")) {
        if (adminTableInterval) clearInterval(adminTableInterval);
        adminTableInterval = setInterval(() => {
            const searchInput = document.getElementById("admin-order-search");
            if (!searchInput || searchInput.value.trim() === '') {
                refreshAdminOrdersTable(false);
            }
        }, 10000);
    }
}

async function checkAdminNewOrders() {
    try {
        const response = await fetch("/api/admin/live-order-poll");
        if (!response.ok) return;
        const data = await response.json();
        if (!data.success) return;

        if (data.has_new_orders && data.notifications && data.notifications.length > 0) {
            updateAdminBadges(data.notifications.length);
            const latestNotif = data.notifications[0];
            if (latestNotif.id > lastSeenNotificationId) {
                lastSeenNotificationId = latestNotif.id;
                
                // 1. Play synthesized bell chime
                if (adminAudioEnabled) {
                    playAlertChime();
                }
                
                // 2. Trigger Toast banner
                showToast(`🔔 ${latestNotif.message}`, "success");

                // 3. Trigger flashing tab title
                flashTitleNotification(latestNotif.message);

                // 4. Trigger desktop push notification
                showDesktopNotification("🥬 New Farm Order Received!", latestNotif.message);
                
                // 5. Trigger Full Screen Modal Pop-up on Admin Dashboard
                if (data.latest_order) {
                    showNewOrderPopup(data.latest_order, latestNotif.id);
                }

                // 6. Instantly refresh the orders table dynamically!
                refreshAdminOrdersTable(false);
            }
        } else {
            updateAdminBadges(0);
        }
    } catch (e) {
        // Silently handle polling network pauses
    }
}

function showNewOrderPopup(order, notifId) {
    const modal = document.getElementById("new-order-popup-modal");
    if (!modal) return;

    const idEl = document.getElementById("popup-order-id");
    const totalEl = document.getElementById("popup-order-total");
    const nameEl = document.getElementById("popup-customer-name");
    const infoEl = document.getElementById("popup-delivery-info");
    const itemsEl = document.getElementById("popup-items-summary");
    const viewBillBtn = document.getElementById("popup-view-bill-btn");

    if (idEl) idEl.innerText = order.order_id;
    if (totalEl) totalEl.innerText = `₹${parseFloat(order.order_total).toFixed(2)}`;
    if (nameEl) nameEl.innerText = `👤 ${order.customer_name} (📞 +91 ${order.customer_phone})`;
    if (infoEl) infoEl.innerText = `📅 ${order.delivery_date} (${order.delivery_slot}) • 📍 ${order.delivery_address}`;
    if (itemsEl) itemsEl.innerText = `🧺 Items: ${order.items_summary || 'Fresh Farm Produce'}`;

    if (viewBillBtn) {
        viewBillBtn.onclick = () => {
            closeNewOrderPopup();
            openInvoiceModal(order.order_id);
        };
    }

    modal.dataset.notifId = notifId;
    modal.classList.remove("hidden");
    setModalScrollLock(true);
}

function closeNewOrderPopup() {
    const modal = document.getElementById("new-order-popup-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

async function acknowledgeAndRefreshOrder() {
    const modal = document.getElementById("new-order-popup-modal");
    const notifId = modal ? modal.dataset.notifId : null;
    
    closeNewOrderPopup();
    try {
        await fetch("/api/admin/dismiss-order-alert", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ notification_id: notifId })
        });
    } catch (e) {}

    // Reload page immediately to update dispatch queue and KPI cards
    window.location.reload();
}

// Real-Time Dynamic Admin Orders Table Refresh, Status Filtering, and Search
let currentAdminStatusFilter = 'all';
let currentAdminSearchQuery = '';
let adminOrdersRefreshDebounce = null;

function handleAdminOrderSearch(query) {
    currentAdminSearchQuery = (query || '').trim();
    clearTimeout(adminOrdersRefreshDebounce);
    adminOrdersRefreshDebounce = setTimeout(() => {
        refreshAdminOrdersTable(false);
    }, 200);
}

function filterAdminOrdersByStatus(status) {
    currentAdminStatusFilter = status;
    document.querySelectorAll('.admin-status-filter-btn').forEach(btn => {
        if (btn.dataset.status === status) {
            btn.className = 'admin-status-filter-btn px-2.5 py-1 text-xs font-bold rounded-lg bg-emerald-700 text-white shadow-xs transition';
        } else {
            btn.className = 'admin-status-filter-btn px-2.5 py-1 text-xs font-bold rounded-lg bg-white border border-gray-200 text-gray-600 hover:bg-gray-100 transition';
        }
    });
    refreshAdminOrdersTable(false);
}

async function refreshAdminOrdersTable(manual = false) {
    const tableBody = document.getElementById("admin-orders-table-body");
    const emptyState = document.getElementById("admin-orders-empty-state");
    const tableWrapper = document.getElementById("admin-orders-table-wrapper");
    const refreshIcon = document.getElementById("admin-refresh-icon");
    const countBadge = document.getElementById("admin-orders-count-badge");
    const countAll = document.getElementById("count-filter-all");

    if (!tableBody) return;

    if (manual && refreshIcon) {
        refreshIcon.classList.add("fa-spin");
    }

    try {
        const url = `/api/admin/orders?status=${encodeURIComponent(currentAdminStatusFilter)}&search=${encodeURIComponent(currentAdminSearchQuery)}`;
        const response = await fetch(url);
        if (!response.ok) return;
        const data = await response.json();
        if (!data.success) return;

        const orders = data.orders || [];
        if (countBadge) countBadge.innerText = `${data.total_count} Orders`;
        if (countAll && currentAdminStatusFilter === 'all' && !currentAdminSearchQuery) {
            countAll.innerText = data.total_count;
        }

        if (orders.length === 0) {
            tableBody.innerHTML = "";
            if (emptyState) emptyState.classList.remove("hidden");
            if (tableWrapper) tableWrapper.classList.add("hidden");
            return;
        }

        if (emptyState) emptyState.classList.add("hidden");
        if (tableWrapper) tableWrapper.classList.remove("hidden");

        tableBody.innerHTML = orders.map(order => {
            const statusClass = 
                order.status === 'Delivered' ? 'bg-emerald-50 text-emerald-800 border-emerald-300' :
                order.status === 'Out for Delivery' ? 'bg-amber-50 text-amber-800 border-amber-300' :
                order.status === 'Packed at Farm' ? 'bg-blue-50 text-blue-800 border-blue-300' :
                order.status === 'Cancelled' ? 'bg-red-50 text-red-800 border-red-300' :
                'bg-indigo-50 text-indigo-800 border-indigo-300';

            return `
                <tr class="hover:bg-emerald-50/30 transition cursor-pointer group" onclick="openAdminOrderDrawer('${order.order_id}')">
                    <td class="px-4 py-4 whitespace-nowrap">
                        <span class="font-mono text-xs font-black text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-lg border border-emerald-100 group-hover:border-emerald-400 transition">
                            ${order.order_id}
                        </span>
                        <div class="text-[10px] text-gray-400 font-semibold mt-1">${order.purchase_date}</div>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap">
                        <div class="font-extrabold text-gray-900">${order.customer_name}</div>
                        <div class="text-xs text-gray-500 font-medium">📞 +91 ${order.customer_phone}</div>
                    </td>
                    <td class="px-4 py-4 text-xs text-gray-700 max-w-xs">
                        <div class="font-bold text-emerald-800">
                            📅 ${order.delivery_date} • ${order.delivery_slot}
                        </div>
                        <p class="text-[11px] text-gray-600 font-medium mt-0.5 line-clamp-2">
                            📍 ${order.delivery_address}
                        </p>
                    </td>
                    <td class="px-4 py-4 text-xs text-gray-800 max-w-xs">
                        <p class="font-semibold line-clamp-2">${order.items_summary}</p>
                        <span class="text-[10px] text-gray-400 font-bold">(${order.item_count} items)</span>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-right font-black text-gray-900 text-sm">
                        ₹${parseFloat(order.order_total).toFixed(2)}
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-center" onclick="event.stopPropagation()">
                        <select onchange="updateOrderStatusAdmin('${order.order_id}', this.value)"
                                class="text-xs font-extrabold px-3 py-1.5 rounded-xl border focus:outline-none focus:ring-2 focus:ring-emerald-500 cursor-pointer shadow-2xs ${statusClass}">
                            <option value="Placed" ${order.status === 'Placed' ? 'selected' : ''}>⏳ Order Placed</option>
                            <option value="Packed at Farm" ${order.status === 'Packed at Farm' ? 'selected' : ''}>📦 Packed at Farm</option>
                            <option value="Out for Delivery" ${order.status === 'Out for Delivery' ? 'selected' : ''}>🚚 Out for Delivery</option>
                            <option value="Delivered" ${order.status === 'Delivered' ? 'selected' : ''}>🟢 Delivered</option>
                            <option value="Cancelled" ${order.status === 'Cancelled' ? 'selected' : ''}>🔴 Cancelled</option>
                        </select>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-center" onclick="event.stopPropagation()">
                        <button onclick="openInvoiceModal('${order.order_id}')" class="bg-gray-100 hover:bg-emerald-50 hover:text-emerald-800 text-gray-700 font-bold p-2 rounded-xl text-xs transition border border-gray-200" title="View / Print Customer Bill">
                            <i class="fa-solid fa-file-invoice"></i>
                        </button>
                    </td>
                    <td class="px-4 py-4 whitespace-nowrap text-center" onclick="event.stopPropagation()">
                        <button onclick="openAdminOrderDrawer('${order.order_id}')" class="bg-emerald-600 hover:bg-emerald-700 text-white font-black text-xs px-3 py-1.5 rounded-xl shadow-xs transition active:scale-95 flex items-center gap-1 mx-auto" title="Inspect Order & Dispatch">
                            <span>Dispatch</span>
                            <i class="fa-solid fa-chevron-right text-[9px]"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');

        if (manual) {
            showToast("Orders refreshed live from database!", "success");
        }
    } catch (e) {
        console.error("Error refreshing admin orders table:", e);
    } finally {
        if (manual && refreshIcon) {
            setTimeout(() => {
                refreshIcon.classList.remove("fa-spin");
            }, 300);
        }
    }
}

// 3-Tone Musical Chime for Orders (698Hz -> 880Hz -> 1046Hz)
function playAlertChime() {
    try {
        const ctx = getAdminAudioContext();
        if (!ctx) return;
        const now = ctx.currentTime;
        
        [
            { freq: 698.46, time: 0.00, dur: 0.18 },
            { freq: 880.00, time: 0.18, dur: 0.20 },
            { freq: 1046.50, time: 0.38, dur: 0.50 }
        ].forEach(note => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = "sine";
            osc.frequency.setValueAtTime(note.freq, now + note.time);
            gain.gain.setValueAtTime(0.35, now + note.time);
            gain.gain.exponentialRampToValueAtTime(0.001, now + note.time + note.dur);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + note.time);
            osc.stop(now + note.time + note.dur);
        });
    } catch (e) {}
}

// Real-time unique customer phone & email availability checkers
let uniqueCheckDebounce = null;
function initUniqueCredentialCheckers() {
    const regPhone = document.getElementById("reg-phone") || document.getElementById("phone");
    const regEmail = document.getElementById("reg-email") || document.getElementById("email");
    const phoneHint = document.getElementById("reg-phone-hint") || document.getElementById("phone-hint");

    if (regPhone) {
        regPhone.addEventListener("input", () => {
            const val = regPhone.value.replace(/[^0-9]/g, '');
            if (val.length === 10) {
                clearTimeout(uniqueCheckDebounce);
                uniqueCheckDebounce = setTimeout(() => {
                    checkCredentialAvailability(val, null, phoneHint);
                }, 300);
            }
        });
    }

    if (regEmail) {
        regEmail.addEventListener("blur", () => {
            const val = regEmail.value.trim();
            if (val.includes("@") && val.includes(".")) {
                checkCredentialAvailability(null, val, null);
            }
        });
    }
}

async function checkCredentialAvailability(phone, email, hintEl) {
    try {
        const params = new URLSearchParams();
        if (phone) params.append("phone", phone);
        if (email) params.append("email", email);

        const res = await fetch(`/api/check-user-unique?${params.toString()}`);
        if (res.ok) {
            const data = await res.json();
            if (phone && hintEl) {
                if (data.phone_available) {
                    hintEl.innerText = "✓ Mobile number available for registration";
                    hintEl.className = "text-[10px] text-emerald-600 mt-1 font-bold";
                } else {
                    hintEl.innerText = data.phone_message || "⚠️ Number already registered to another account";
                    hintEl.className = "text-[10px] text-red-600 mt-1 font-bold animate-pulse";
                }
            }
            if (email && !data.email_available) {
                showToast(`⚠️ Email ${email} is already in use by an existing account!`, "error");
            }
        }
    } catch (e) {}
}

// =========================================================================
// COMMERCIAL FEATURES: FARM WALLET & CASHBACK
// =========================================================================

// Fetch customer's live wallet balance & passbook
async function fetchUserWalletBalance() {
    try {
        const res = await fetch("/api/user/wallet");
        if (res.ok) {
            const data = await res.json();
            if (data.success) {
                userWalletBalance = parseFloat(data.balance) || 0.0;
                
                const walletEl = document.getElementById("cart-wallet-balance");
                if (walletEl) walletEl.innerText = `₹${userWalletBalance.toFixed(2)}`;
                
                const navWalletEl = document.getElementById("nav-wallet-balance");
                if (navWalletEl) navWalletEl.innerText = `₹${Math.round(userWalletBalance)}`;
                
                const toggle = document.getElementById("use-wallet-toggle");
                if (toggle && userWalletBalance <= 0) {
                    toggle.disabled = true;
                }
            }
        }
    } catch (e) {}
}

// Toggle Farm Wallet Coin redemption in checkout drawer
function toggleWalletRedemption() {
    const toggle = document.getElementById("use-wallet-toggle");
    isWalletApplied = toggle ? toggle.checked : false;
    updateCartUI();
    if (isWalletApplied && walletDeductedAmount > 0) {
        showToast(`Redeemed ₹${walletDeductedAmount.toFixed(2)} in Farm Wallet Coins! 🪙`, "success");
    }
}

// =========================================================================
// COMMERCIAL FEATURES: VOICE SEARCH (SPEECH-TO-TEXT)
// =========================================================================

// Pulsing Mic Web Speech API Voice Search (English & Telugu)
function startVoiceSearch() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast("Voice search is not supported in this browser. Please try Chrome, Edge, or a mobile browser.", "error");
        return;
    }

    const micIcon = document.getElementById("voice-mic-icon");

    if (isListeningVoice && speechRecognitionInstance) {
        speechRecognitionInstance.stop();
        isListeningVoice = false;
        if (micIcon) micIcon.className = "w-8 h-8 rounded-xl bg-white/20 hover:bg-white/30 flex items-center justify-center text-xs shadow-xs text-emerald-200";
        return;
    }

    try {
        const recognition = new SpeechRecognition();
        speechRecognitionInstance = recognition;
        recognition.lang = 'en-IN'; // Transcribes Indian English and phonetically transcribed Telugu produce terms
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            isListeningVoice = true;
            if (micIcon) {
                micIcon.className = "w-8 h-8 rounded-xl bg-red-600 text-white flex items-center justify-center text-xs shadow-lg animate-pulse";
            }
            showToast("🎙️ Listening... Speak vegetable name (e.g. 'Tomato', 'Palak', 'టమోటా')", "info");
        };

        recognition.onresult = (event) => {
            let transcript = event.results[0][0].transcript.trim().toLowerCase();
            transcript = transcript.replace(/[.,/#!$%^&*;:{}=\-_`~()]/g, "").trim();
            
            const searchInput = document.getElementById("search-input");
            if (searchInput) {
                searchInput.value = transcript;
                searchProducts();
            }
            showToast(`Voice detected: "${transcript}" 🥕`, "success");
        };

        recognition.onerror = (event) => {
            console.warn("Speech recognition notice:", event.error);
            if (event.error === 'not-allowed') {
                showToast("Microphone access denied. Please allow microphone permissions in browser.", "error");
            } else if (event.error !== 'no-speech') {
                showToast(`Voice search: ${event.error}`, "info");
            }
            isListeningVoice = false;
            if (micIcon) micIcon.className = "w-8 h-8 rounded-xl bg-white/20 hover:bg-white/30 flex items-center justify-center text-xs shadow-xs text-emerald-200";
        };

        recognition.onend = () => {
            isListeningVoice = false;
            if (micIcon) micIcon.className = "w-8 h-8 rounded-xl bg-white/20 hover:bg-white/30 flex items-center justify-center text-xs shadow-xs text-emerald-200";
        };

        recognition.start();
    } catch (err) {
        console.error("Voice search initialization error:", err);
        showToast("Unable to start microphone for voice search.", "error");
        isListeningVoice = false;
        if (micIcon) micIcon.className = "w-8 h-8 rounded-xl bg-white/20 hover:bg-white/30 flex items-center justify-center text-xs shadow-xs text-emerald-200";
    }
}

// =========================================================================
// COMMERCIAL FEATURES: VEGETABLE HEALTH & NUTRITION FACTSHEET MODAL
// =========================================================================

// Open Farm Factsheet Modal with Nutrition, Telugu Pairings, and Reviews
async function openProduceDetailsModal(pid) {
    const modal = document.getElementById("produce-detail-modal");
    const content = document.getElementById("produce-modal-content");
    if (!modal || !content) return;

    modal.classList.remove("hidden");
    setModalScrollLock(true);
    content.innerHTML = `
        <div class="p-10 text-center text-gray-500">
            <i class="fa-solid fa-circle-notch fa-spin text-emerald-600 text-3xl mb-3"></i>
            <p class="text-sm font-extrabold text-gray-800">Harvesting Farm Factsheet...</p>
            <p class="text-xs text-gray-400 mt-1">Retrieving organic nutrition profile & reviews</p>
        </div>
    `;

    try {
        const response = await fetch(`/api/product/${pid}/details`);
        if (!response.ok) throw new Error("Failed to load produce factsheet");
        const data = await response.json();
        if (!data.success) throw new Error(data.error || "Produce not found");

        const prod = data.product;
        const reviews = data.reviews || [];
        const nut = data.nutrition || {};

        const engName = prod.name.split('[')[0].trim();
        const teluguName = prod.name.includes('[') ? prod.name.split('[')[1].replace(']', '').trim() : '';

        let reviewsHtml = '';
        if (reviews.length === 0) {
            reviewsHtml = `
                <div class="p-4 bg-gray-50 rounded-2xl border border-gray-100 text-center text-xs text-gray-400">
                    No customer reviews yet. Be the first family to rate this harvest!
                </div>
            `;
        } else {
            reviews.forEach(rev => {
                const starCount = Math.min(5, Math.max(1, Math.round(rev.rating || 5)));
                const stars = '⭐'.repeat(starCount);
                reviewsHtml += `
                    <div class="p-3 bg-gray-50/80 rounded-2xl border border-gray-100 space-y-1">
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="text-xs font-black text-gray-900">${escapeHtml(rev.user_name || 'Verified Customer')}</span>
                                <span class="text-[9px] font-bold bg-emerald-100 text-emerald-800 px-1.5 py-0.2 rounded-md">✓ Verified Harvest Buyer</span>
                            </div>
                            <span class="text-xs">${stars}</span>
                        </div>
                        <p class="text-xs text-gray-600 font-medium leading-relaxed">${escapeHtml(rev.comment || '')}</p>
                        <p class="text-[9px] text-gray-400">${rev.created_at || ''}</p>
                    </div>
                `;
            });
        }

        content.innerHTML = `
            <!-- Modal Header -->
            <div class="bg-gradient-to-r from-emerald-800 via-emerald-700 to-green-700 p-6 text-white relative">
                <button onclick="closeProduceDetailsModal()" class="absolute top-4 right-4 text-white/80 hover:text-white p-2 rounded-full hover:bg-white/10 transition">
                    <i class="fa-solid fa-xmark text-lg"></i>
                </button>
                <div class="flex items-center gap-4">
                    <div class="w-16 h-16 rounded-2xl bg-white/20 backdrop-blur-md flex items-center justify-center text-4xl shadow-inner border border-white/20">
                        ${prod.image_url || '🥬'}
                    </div>
                    <div>
                        <span class="text-[10px] font-black uppercase tracking-wider bg-white/20 px-2 py-0.5 rounded-md">
                            ${prod.category} • 100% Organic
                        </span>
                        <h3 class="text-xl font-black text-white leading-tight mt-1">${engName}</h3>
                        ${teluguName ? `
                            <p class="text-xs font-extrabold text-emerald-200 mt-0.5">తెలుగు: [ ${teluguName} ]</p>
                        ` : ''}
                        <div class="flex items-center gap-2 mt-2">
                            <span class="text-lg font-black text-amber-300">₹${prod.price.toFixed(2)}</span>
                            <span class="text-xs text-emerald-100">per ${prod.unit}</span>
                            <span class="ml-2 inline-flex items-center gap-1 bg-amber-400/20 text-amber-200 border border-amber-300/30 px-2 py-0.5 rounded-lg text-xs font-black">
                                ⭐ ${(prod.rating || 4.8).toFixed(1)} (${prod.review_count || 28} reviews)
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Modal Content Body -->
            <div class="p-6 space-y-6">
                <!-- Description -->
                <div>
                    <h4 class="text-xs font-black text-gray-400 uppercase tracking-wider mb-1">Harvest Overview</h4>
                    <p class="text-xs text-gray-700 font-medium leading-relaxed">${prod.description}</p>
                </div>

                <!-- Nutritional Profile Grid -->
                <div>
                    <h4 class="text-xs font-black text-gray-400 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
                        <i class="fa-solid fa-apple-whole text-emerald-600"></i> Nutritional Profile (Per 100g)
                    </h4>
                    <div class="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-center">
                        <div class="p-2.5 bg-emerald-50/70 border border-emerald-100 rounded-2xl">
                            <span class="text-[10px] font-bold text-gray-500 uppercase block">Calories</span>
                            <span class="text-sm font-black text-emerald-800">${nut.calories || '25 kcal'}</span>
                        </div>
                        <div class="p-2.5 bg-emerald-50/70 border border-emerald-100 rounded-2xl">
                            <span class="text-[10px] font-bold text-gray-500 uppercase block">Dietary Fiber</span>
                            <span class="text-sm font-black text-emerald-800">${nut.fiber || '2.8g'}</span>
                        </div>
                        <div class="p-2.5 bg-emerald-50/70 border border-emerald-100 rounded-2xl">
                            <span class="text-[10px] font-bold text-gray-500 uppercase block">Protein</span>
                            <span class="text-sm font-black text-emerald-800">${nut.protein || '1.2g'}</span>
                        </div>
                        <div class="p-2.5 bg-emerald-50/70 border border-emerald-100 rounded-2xl">
                            <span class="text-[10px] font-bold text-gray-500 uppercase block">Key Vitamin</span>
                            <span class="text-sm font-black text-emerald-800">${nut.vitamins ? nut.vitamins.split(',')[0] : 'Vit C'}</span>
                        </div>
                    </div>
                </div>

                <!-- Health & Immunity Benefits -->
                <div class="p-3.5 bg-amber-50/70 border border-amber-200/80 rounded-2xl space-y-1.5">
                    <div class="flex items-center gap-1.5 text-amber-900 font-black text-xs">
                        <i class="fa-solid fa-heart-pulse text-amber-600"></i>
                        <span>Health & Immunity Benefits</span>
                    </div>
                    <p class="text-xs text-amber-950 font-medium leading-relaxed">
                        ${nut.benefits || 'Rich in natural antioxidants and essential dietary fiber supporting digestive wellness and immune resistance.'}
                    </p>
                </div>

                <!-- Telugu Culinary Pairings -->
                <div class="p-3.5 bg-emerald-50/70 border border-emerald-200/80 rounded-2xl space-y-1.5">
                    <div class="flex items-center gap-1.5 text-emerald-950 font-black text-xs">
                        <i class="fa-solid fa-utensils text-emerald-700"></i>
                        <span>Traditional Telugu Culinary Pairings</span>
                    </div>
                    <p class="text-xs text-emerald-900 font-medium leading-relaxed">
                        ${nut.culinary_use || 'Perfect for traditional Andhra Pappu, fry curries (Vepudu), sambar, and authentic rasam.'}
                    </p>
                </div>

                <!-- Customer Reviews Section -->
                <div>
                    <div class="flex items-center justify-between mb-2.5">
                        <h4 class="text-xs font-black text-gray-700 uppercase tracking-wider flex items-center gap-1.5">
                            <i class="fa-solid fa-star text-amber-400"></i> Verified Customer Reviews (${reviews.length})
                        </h4>
                        <span class="text-[11px] font-extrabold text-emerald-700">⭐ ${(prod.rating || 4.8).toFixed(1)} / 5.0</span>
                    </div>
                    <div class="space-y-2 max-h-48 overflow-y-auto pr-1">
                        ${reviewsHtml}
                    </div>
                </div>
            </div>

            <!-- Modal Footer with 1-Click ADD to Basket -->
            <div class="p-4 bg-gray-50 border-t border-gray-100 flex items-center justify-between">
                <div>
                    <span class="text-[9px] text-gray-400 font-bold uppercase block">Stock Status</span>
                    <span class="text-xs font-black ${prod.stock > 0 ? 'text-emerald-700' : 'text-red-600'}">
                        ${prod.stock > 0 ? `🟢 In Stock (${prod.stock} units)` : '🔴 Sold Out'}
                    </span>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="closeProduceDetailsModal()" class="px-3.5 py-2 bg-white hover:bg-gray-100 text-gray-700 font-extrabold text-xs rounded-xl border border-gray-200 transition">
                        Close
                    </button>
                    ${prod.stock > 0 ? `
                        <button onclick="addToCartRealtime(${prod.id}, 1); closeProduceDetailsModal();" class="px-5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white font-black text-xs rounded-xl shadow-md transition active:scale-95 flex items-center gap-1.5">
                            <i class="fa-solid fa-plus text-[10px]"></i>
                            <span>Add to Basket</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    } catch (e) {
        content.innerHTML = `
            <div class="p-8 text-center text-red-500 space-y-2">
                <i class="fa-solid fa-triangle-exclamation text-3xl mb-2"></i>
                <p class="text-sm font-bold">${e.message}</p>
                <button onclick="closeProduceDetailsModal()" class="mt-2 px-4 py-1.5 bg-gray-100 text-gray-700 rounded-xl text-xs font-bold">Close</button>
            </div>
        `;
    }
}

function closeProduceDetailsModal() {
    const modal = document.getElementById("produce-detail-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

// =========================================================================
// COMMERCIAL FEATURES: CUSTOMER STAR RATINGS & REVIEWS
// =========================================================================

// Open modal for rating delivered produce
function openReviewModal(productId, productName) {
    const modal = document.getElementById("review-modal");
    if (!modal) return;

    const idInput = document.getElementById("review-product-id");
    const titleEl = document.getElementById("review-product-title");
    const commentInput = document.getElementById("review-comment-input");

    if (idInput) idInput.value = productId;
    if (titleEl) titleEl.innerText = productName;
    if (commentInput) commentInput.value = "";
    selectStarRating(5);

    modal.classList.remove("hidden");
    setModalScrollLock(true);
}

// Close review modal
function closeReviewModal() {
    const modal = document.getElementById("review-modal");
    if (modal) modal.classList.add("hidden");
    setModalScrollLock(false);
}

// Select star rating 1-5
function selectStarRating(val) {
    const ratingVal = document.getElementById("review-rating-val");
    if (ratingVal) ratingVal.value = val;

    const btns = document.querySelectorAll(".star-rating-btn");
    btns.forEach(btn => {
        const star = parseInt(btn.dataset.star);
        if (star <= val) {
            btn.classList.add("text-amber-400");
            btn.classList.remove("text-gray-300");
        } else {
            btn.classList.remove("text-amber-400");
            btn.classList.add("text-gray-300");
        }
    });

    const label = document.getElementById("star-rating-label");
    if (label) {
        const DESCS = {
            5: "5.0 / 5.0 - Super Fresh Harvest! ⭐⭐⭐⭐⭐",
            4: "4.0 / 5.0 - Very Good Quality! ⭐⭐⭐⭐",
            3: "3.0 / 5.0 - Average Quality ⭐⭐⭐",
            2: "2.0 / 5.0 - Needs Improvement ⭐⭐",
            1: "1.0 / 5.0 - Poor Freshness ⭐"
        };
        label.innerText = DESCS[val] || `${val}.0 / 5.0`;
    }
}

// Submit produce review to backend
async function handleReviewSubmit(e) {
    e.preventDefault();
    const pid = document.getElementById("review-product-id") ? document.getElementById("review-product-id").value : null;
    const rating = document.getElementById("review-rating-val") ? document.getElementById("review-rating-val").value : 5;
    const comment = document.getElementById("review-comment-input") ? document.getElementById("review-comment-input").value.trim() : "";

    if (!pid || !comment) {
        showToast("Please provide your review comment before submitting!", "error");
        return;
    }

    try {
        const response = await fetch("/api/product/review", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                product_id: parseInt(pid),
                rating: parseFloat(rating),
                comment: comment
            })
        });

        const data = await response.json();
        if (data.success) {
            showToast("Thank you! Your verified harvest rating has been posted. ⭐", "success");
            closeReviewModal();
            setTimeout(() => window.location.reload(), 1000);
        } else {
            showToast(data.error || "Failed to submit review", "error");
        }
    } catch (err) {
        showToast("Network error submitting review", "error");
    }
}

// =========================================================
// 24/7 KISAN AI CUSTOMER SUPPORT CHATBOT CONTROLLER
// =========================================================

let farmAIChatInitialized = false;

function toggleFarmAIChat() {
    const chatWin = document.getElementById("farm-ai-chat-window");
    if (!chatWin) return;

    const isHidden = chatWin.classList.contains("hidden") || chatWin.style.display === "none";
    if (isHidden) {
        chatWin.classList.remove("hidden");
        chatWin.style.display = "flex";
        if (!farmAIChatInitialized) {
            initFarmAIChat();
        }
        const input = document.getElementById("farm-ai-input");
        if (input) setTimeout(() => input.focus(), 150);
    } else {
        chatWin.classList.add("hidden");
        chatWin.style.display = "none";
    }
}

function clearFarmAIChat() {
    const container = document.getElementById("farm-ai-messages-container");
    if (container) container.innerHTML = "";
    farmAIChatInitialized = false;
    initFarmAIChat();
}

function initFarmAIChat() {
    const container = document.getElementById("farm-ai-messages-container");
    if (!container) return;
    farmAIChatInitialized = true;

    container.innerHTML = `
        <div class="flex items-start gap-2.5">
            <div class="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center text-base flex-shrink-0 shadow-xs border border-emerald-200">
                🌾
            </div>
            <div class="bg-white border border-emerald-100/90 rounded-2xl rounded-tl-xs p-3.5 shadow-xs max-w-[85%] text-gray-800 space-y-2">
                <p class="font-extrabold text-emerald-950 text-xs flex items-center gap-1.5">
                    <span>Kisan AI</span>
                    <span class="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-full border border-emerald-100">Farm Assistant</span>
                </p>
                <p class="text-xs leading-relaxed text-gray-700">
                    Namaste! 🙏 Welcome to Vamsi Organic Farms. I'm here 24/7 to help you with <strong>today's harvest availability</strong>, <strong>live delivery tracking</strong>, <strong>authentic Andhra recipes</strong>, <strong>wallet coins</strong>, and any customer support needs!
                </p>
            </div>
        </div>
    `;

    renderFarmAISuggestionChips([
        "🥬 In-Stock Produce",
        "🚚 Track My Order",
        "🪙 Wallet Coins & Cashback",
        "🍛 Andhra Recipe Ideas",
        "🏷️ Active Coupons",
        "🌿 Organic Assurance"
    ]);
}

function renderFarmAISuggestionChips(chips) {
    const bar = document.getElementById("farm-ai-chips-bar");
    if (!bar) return;
    if (!chips || chips.length === 0) {
        bar.innerHTML = "";
        return;
    }

    bar.innerHTML = chips.map(chip => `
        <button type="button" onclick="sendFarmAIMessage('${chip.replace(/'/g, "\\'")}')"
                class="px-2.5 py-1 rounded-full bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200/80 font-bold transition active:scale-95 flex-shrink-0 text-[11px]">
            ${chip}
        </button>
    `).join("");
}

function formatFarmAIMarkdown(text) {
    if (!text) return "";
    let html = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/### (.*?)\n/g, '<h4 class="font-black text-gray-900 text-xs mt-1.5 mb-1">$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="font-extrabold text-gray-900">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="text-gray-700 italic">$1</em>')
        .replace(/`([^`]+)`/g, '<code class="font-mono text-[10px] bg-emerald-50 text-emerald-900 px-1 py-0.5 rounded border border-emerald-100">$1</code>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');
    return html;
}

async function submitFarmAIChat(e) {
    if (e) e.preventDefault();
    const input = document.getElementById("farm-ai-input");
    if (!input) return;
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    await sendFarmAIMessage(msg);
}

async function sendFarmAIMessage(userText) {
    const container = document.getElementById("farm-ai-messages-container");
    if (!container) return;

    if (!farmAIChatInitialized) {
        initFarmAIChat();
    }

    // Append User Message
    const userBubble = document.createElement("div");
    userBubble.className = "flex items-start justify-end gap-2";
    userBubble.innerHTML = `
        <div class="bg-gradient-to-r from-emerald-600 to-green-600 text-white rounded-2xl rounded-tr-xs p-3 shadow-sm max-w-[85%] text-xs font-semibold leading-relaxed">
            ${userText.replace(/</g, "&lt;").replace(/>/g, "&gt;")}
        </div>
        <div class="w-7 h-7 rounded-xl bg-emerald-800 text-white flex items-center justify-center text-xs flex-shrink-0 shadow-xs">
            <i class="fa-solid fa-user"></i>
        </div>
    `;
    container.appendChild(userBubble);
    container.scrollTop = container.scrollHeight;

    // Append Typing Indicator
    const typingId = "farm-ai-typing-" + Date.now();
    const typingBubble = document.createElement("div");
    typingBubble.id = typingId;
    typingBubble.className = "flex items-start gap-2.5 animate-pulse";
    typingBubble.innerHTML = `
        <div class="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center text-base flex-shrink-0 shadow-xs border border-emerald-200">
            🌾
        </div>
        <div class="bg-white border border-gray-100 rounded-2xl rounded-tl-xs p-3 shadow-xs text-xs text-gray-500 font-medium flex items-center gap-1.5">
            <span>Kisan AI is typing</span>
            <span class="flex gap-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-bounce"></span>
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-bounce [animation-delay:0.2s]"></span>
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-bounce [animation-delay:0.4s]"></span>
            </span>
        </div>
    `;
    container.appendChild(typingBubble);
    container.scrollTop = container.scrollHeight;

    try {
        const response = await fetch("/api/ai-assistant/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: userText })
        });
        const data = await response.json();

        // Remove typing indicator
        const typingElem = document.getElementById(typingId);
        if (typingElem) typingElem.remove();

        if (data.success) {
            const botBubble = document.createElement("div");
            botBubble.className = "flex items-start gap-2.5";
            botBubble.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-emerald-100 text-emerald-800 flex items-center justify-center text-base flex-shrink-0 shadow-xs border border-emerald-200">
                    🌾
                </div>
                <div class="bg-white border border-emerald-100/90 rounded-2xl rounded-tl-xs p-3.5 shadow-xs max-w-[85%] text-gray-800 space-y-2 leading-relaxed">
                    <p class="font-extrabold text-emerald-950 text-xs flex items-center gap-1.5">
                        <span>Kisan AI</span>
                        <span class="text-[9px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded-full border border-emerald-100">Verified Answer</span>
                    </p>
                    <div class="text-xs text-gray-700 space-y-1">
                        ${formatFarmAIMarkdown(data.reply)}
                    </div>
                </div>
            `;
            container.appendChild(botBubble);
            container.scrollTop = container.scrollHeight;

            // Update suggestions
            if (data.suggestions) {
                renderFarmAISuggestionChips(data.suggestions);
            }
        } else {
            const errBubble = document.createElement("div");
            errBubble.className = "flex items-start gap-2.5";
            errBubble.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-red-100 text-red-700 flex items-center justify-center text-base flex-shrink-0">
                    ⚠️
                </div>
                <div class="bg-red-50 border border-red-200 rounded-2xl rounded-tl-xs p-3 shadow-xs max-w-[85%] text-xs text-red-800 font-bold">
                    ${data.error || "I could not process your question right now. Please try again!"}
                </div>
            `;
            container.appendChild(errBubble);
            container.scrollTop = container.scrollHeight;
        }
    } catch (err) {
        const typingElem = document.getElementById(typingId);
        if (typingElem) typingElem.remove();

        const errBubble = document.createElement("div");
        errBubble.className = "flex items-start gap-2.5";
        errBubble.innerHTML = `
            <div class="w-8 h-8 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center text-base flex-shrink-0">
                ⚡
            </div>
            <div class="bg-amber-50 border border-amber-200 rounded-2xl rounded-tl-xs p-3 shadow-xs max-w-[85%] text-xs text-amber-900 font-bold">
                Network connection hiccup. Please try again in a moment!
            </div>
        `;
        container.appendChild(errBubble);
        container.scrollTop = container.scrollHeight;
    }
}

// =========================================================================
// MULTILINGUAL (ENGLISH + TELUGU PHONETIC) & FUZZY SEARCH OPTIMIZATION
// =========================================================================

const TELUGU_VEG_DICTIONARY = {
    'tamata': ['tomato', 'టమోటా', 'tamato', 'thakkali'],
    'tomato': ['tamata', 'టమోటా', 'thakkali'],
    'టమోటా': ['tomato', 'tamata'],
    'ullipaya': ['onion', 'ఉల్లిపాయ', 'ulli', 'eerulli', 'piyaz'],
    'ulli': ['onion', 'ఉల్లిపాయ', 'ullipaya'],
    'onion': ['ullipaya', 'ఉల్లిపాయ', 'ulli', 'piyaz'],
    'ఉల్లిపాయ': ['onion', 'ullipaya'],
    'aloo': ['potato', 'బంగాళాదుంప', 'bangaladumpa', 'batata'],
    'potato': ['aloo', 'బంగాళాదుంప', 'bangaladumpa'],
    'bangaladumpa': ['potato', 'aloo', 'బంగాళాదుంప'],
    'బంగాళాదుంప': ['potato', 'aloo'],
    'bendakaya': ['okra', 'బెండకాయ', 'bhendi', 'bhindi', 'ladies finger'],
    'bhindi': ['okra', 'బెండకాయ', 'bendakaya'],
    'okra': ['bendakaya', 'బెండకాయ', 'bhindi', 'bhendi'],
    'బెండకాయ': ['okra', 'bendakaya', 'bhindi'],
    'vankaya': ['brinjal', 'వంకాయ', 'baingan', 'eggplant'],
    'baingan': ['brinjal', 'వంకాయ', 'vankaya'],
    'brinjal': ['vankaya', 'వంకాయ', 'baingan', 'eggplant'],
    'వంకాయ': ['brinjal', 'vankaya'],
    'mirapa': ['chilli', 'మిరపకాయ', 'mirchi', 'chili'],
    'mirchi': ['chilli', 'మిరపకాయ', 'mirapa', 'pachi mirchi'],
    'chilli': ['mirchi', 'మిరపకాయ', 'mirapa', 'pachi mirchi'],
    'chili': ['chilli', 'mirchi', 'మిరపకాయ'],
    'మిరపకాయ': ['chilli', 'mirchi', 'mirapa'],
    'palak': ['spinach', 'పాలకూర', 'palakoora'],
    'palakoora': ['spinach', 'పాలకూర', 'palak'],
    'spinach': ['palak', 'పాలకూర', 'palakoora'],
    'పాలకూర': ['spinach', 'palak'],
    'kothimeera': ['coriander', 'కొత్తిమీర', 'dhaniya'],
    'coriander': ['kothimeera', 'కొత్తిమీర', 'dhaniya'],
    'కొత్తిమీర': ['coriander', 'kothimeera'],
    'pudina': ['mint', 'పుదీనా'],
    'mint': ['pudina', 'పుదీనా'],
    'పుదీనా': ['mint', 'pudina'],
    'carrot': ['carret', 'క్యారెట్', 'gajjara'],
    'క్యారెట్': ['carrot', 'carret'],
    'sorakaya': ['bottle gourd', 'సొరకాయ', 'anapakaya', 'lauki'],
    'anapakaya': ['bottle gourd', 'సొరకాయ', 'sorakaya'],
    'bottle gourd': ['sorakaya', 'సొరకాయ', 'lauki'],
    'సొరకాయ': ['bottle gourd', 'sorakaya'],
    'kakarakaya': ['bitter gourd', 'కాకరకాయ', 'karela'],
    'karela': ['bitter gourd', 'కాకరకాయ', 'kakarakaya'],
    'bitter gourd': ['kakarakaya', 'కాకరకాయ', 'karela'],
    'కాకరకాయ': ['bitter gourd', 'kakarakaya'],
    'beerakaya': ['ridge gourd', 'బీరకాయ', 'turai'],
    'ridge gourd': ['beerakaya', 'బీరకాయ', 'turai'],
    'బీరకాయ': ['ridge gourd', 'beerakaya'],
    'dosakaya': ['cucumber', 'దోసకాయ', 'keera', 'kheera'],
    'cucumber': ['dosakaya', 'దోసకాయ', 'keera', 'kheera'],
    'keera': ['cucumber', 'దోసకాయ', 'dosakaya'],
    'దోసకాయ': ['cucumber', 'dosakaya'],
    'chikkudukaya': ['beans', 'చిక్కుడుకాయ'],
    'beans': ['chikkudukaya', 'చిక్కుడుకాయ'],
    'చిక్కుడుకాయ': ['beans', 'chikkudukaya'],
    'cauliflower': ['గోబీ', 'gobi', 'cauliflower'],
    'cabbage': ['క్యాబేజీ', 'patta gobi', 'cabbage'],
    'ginger': ['allam', 'అల్లం', 'adrak'],
    'allam': ['ginger', 'అల్లం', 'adrak'],
    'garlic': ['vellulli', 'వెల్లుల్లి', 'lahsun'],
    'vellulli': ['garlic', 'వెల్లుల్లి', 'lahsun'],
    'lemon': ['nimakaya', 'నిమ్మకాయ', 'nimbu'],
    'nimakaya': ['lemon', 'నిమ్మకాయ', 'nimbu']
};

function calculateLevenshtein(a, b) {
    if (!a || !b) return (a || b || '').length;
    const m = a.length, n = b.length;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = 0; i <= m; i++) dp[i][0] = i;
    for (let j = 0; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++) {
        for (let j = 1; j <= n; j++) {
            if (a[i - 1] === b[j - 1]) dp[i][j] = dp[i - 1][j - 1];
            else dp[i][j] = Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1]) + 1;
        }
    }
    return dp[m][n];
}

function performOptimizedSearch() {
    const searchInput = document.getElementById("search-input");
    const clearBtn = document.getElementById("search-clear-btn");
    const countDisplay = document.getElementById("product-count-display");
    const emptyState = document.getElementById("search-empty-state");
    const emptyQueryText = document.getElementById("empty-query-text");

    const rawQuery = (searchInput ? searchInput.value : "").trim();
    const query = rawQuery.toLowerCase();

    // Toggle clear button visibility
    if (clearBtn) {
        if (query.length > 0) {
            clearBtn.classList.remove("hidden");
            clearBtn.style.display = "flex";
        } else {
            clearBtn.classList.add("hidden");
            clearBtn.style.display = "none";
        }
    }

    const cards = document.querySelectorAll(".product-card");
    if (!cards || cards.length === 0) return;

    if (query === "") {
        cards.forEach(card => card.style.display = "flex");
        if (emptyState) {
            emptyState.classList.add("hidden");
            emptyState.style.display = "none";
        }
        if (countDisplay) {
            countDisplay.innerHTML = `<strong>${cards.length}</strong> Farm Vegetables in Stock`;
        }
        return;
    }

    // Tokenize multi-word search
    const tokens = query.split(/\s+/).filter(t => t.length > 0);
    const expandedTokens = new Set(tokens);

    tokens.forEach(tok => {
        if (TELUGU_VEG_DICTIONARY[tok]) {
            TELUGU_VEG_DICTIONARY[tok].forEach(syn => expandedTokens.add(syn.toLowerCase()));
        }
        for (const [key, syns] of Object.entries(TELUGU_VEG_DICTIONARY)) {
            if (key.includes(tok) || tok.includes(key)) {
                syns.forEach(s => expandedTokens.add(s.toLowerCase()));
            }
        }
    });

    let visibleCount = 0;

    cards.forEach(card => {
        const name = (card.dataset.name || "").toLowerCase();
        const tags = (card.dataset.tags || "").toLowerCase();
        const category = (card.dataset.category || "").toLowerCase();
        const fullContent = `${name} ${tags} ${category}`;

        let matches = false;

        for (const token of expandedTokens) {
            if (fullContent.includes(token)) {
                matches = true;
                break;
            }
            if (token.length >= 4) {
                const words = fullContent.split(/\s+/);
                for (const w of words) {
                    if (w.length >= 4 && calculateLevenshtein(token, w) <= 1) {
                        matches = true;
                        break;
                    }
                }
                if (matches) break;
            }
        }

        if (matches) {
            card.style.display = "flex";
            visibleCount++;
        } else {
            card.style.display = "none";
        }
    });

    if (countDisplay) {
        if (visibleCount === cards.length) {
            countDisplay.innerHTML = `<strong>${cards.length}</strong> Farm Vegetables in Stock`;
        } else {
            countDisplay.innerHTML = `Showing <strong>${visibleCount}</strong> of ${cards.length} vegetables`;
        }
    }

    if (emptyState) {
        if (visibleCount === 0) {
            if (emptyQueryText) emptyQueryText.innerText = rawQuery;
            emptyState.classList.remove("hidden");
            emptyState.style.display = "block";
        } else {
            emptyState.classList.add("hidden");
            emptyState.style.display = "none";
        }
    }
}

function clearSearchInput() {
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.value = "";
        searchInput.focus();
    }
    performOptimizedSearch();
}

function setQuickSearch(term) {
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.value = term;
        searchInput.focus();
    }
    performOptimizedSearch();
}

// Attach globally
window.searchProducts = performOptimizedSearch;
window.performOptimizedSearch = performOptimizedSearch;
window.clearSearchInput = clearSearchInput;
window.setQuickSearch = setQuickSearch;

// ==========================================
// 📱 PWA (Progressive Web App) Install Engine
// ==========================================
let pwaDeferredPrompt = null;

function isAppStandalone() {
    return window.matchMedia('(display-mode: standalone)').matches ||
           window.navigator.standalone === true ||
           document.referrer.includes('android-app://');
}

function isIosDevice() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream;
}

function initPwaInstaller() {
    // If already launched as installed standalone PWA app, keep install prompts hidden
    if (isAppStandalone()) {
        const banner = document.getElementById("pwa-install-banner");
        const navBtn = document.getElementById("pwa-install-nav-btn");
        if (banner) banner.classList.add("hidden");
        if (navBtn) navBtn.classList.add("hidden");
        return;
    }

    // Capture the beforeinstallprompt event (Chrome, Edge, Android, Chromium browsers)
    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        pwaDeferredPrompt = e;

        // Show header navbar install button
        const navBtn = document.getElementById("pwa-install-nav-btn");
        if (navBtn) {
            navBtn.classList.remove("hidden");
            navBtn.classList.add("inline-flex");
        }

        // Show floating install banner if not dismissed in last 24 hours
        const banner = document.getElementById("pwa-install-banner");
        const dismissedAt = localStorage.getItem("pwa_banner_dismissed_at");
        const now = Date.now();
        const oneDay = 24 * 60 * 60 * 1000;

        if (banner && (!dismissedAt || (now - parseInt(dismissedAt, 10)) > oneDay)) {
            setTimeout(() => {
                banner.classList.remove("hidden");
            }, 2000);
        }
    });

    // On iOS Safari: show nav button & polite banner
    if (isIosDevice() && !isAppStandalone()) {
        const navBtn = document.getElementById("pwa-install-nav-btn");
        if (navBtn) {
            navBtn.classList.remove("hidden");
            navBtn.classList.add("inline-flex");
        }

        const banner = document.getElementById("pwa-install-banner");
        const dismissedAt = localStorage.getItem("pwa_banner_dismissed_at");
        const now = Date.now();
        const oneDay = 24 * 60 * 60 * 1000;

        if (banner && (!dismissedAt || (now - parseInt(dismissedAt, 10)) > oneDay)) {
            setTimeout(() => {
                banner.classList.remove("hidden");
            }, 2500);
        }
    }

    // Detect when user successfully installs
    window.addEventListener('appinstalled', () => {
        pwaDeferredPrompt = null;
        const banner = document.getElementById("pwa-install-banner");
        const navBtn = document.getElementById("pwa-install-nav-btn");
        if (banner) banner.classList.add("hidden");
        if (navBtn) navBtn.classList.add("hidden");
        if (typeof showToast === 'function') {
            showToast("🎉 PPM Organic Farms App installed successfully! Enjoy 1-tap fresh vegetable delivery.", "success");
        }
    });
}

async function triggerPwaInstall() {
    if (pwaDeferredPrompt) {
        // Show native browser install prompt
        pwaDeferredPrompt.prompt();
        const choiceResult = await pwaDeferredPrompt.userChoice;
        if (choiceResult && choiceResult.outcome === 'accepted') {
            const banner = document.getElementById("pwa-install-banner");
            const navBtn = document.getElementById("pwa-install-nav-btn");
            if (banner) banner.classList.add("hidden");
            if (navBtn) navBtn.classList.add("hidden");
            if (typeof showToast === 'function') {
                showToast("Installing PPM Organic Farms App...", "success");
            }
        }
        pwaDeferredPrompt = null;
    } else if (isIosDevice()) {
        // Show iOS Add to Home Screen step-by-step modal
        const modal = document.getElementById("ios-install-modal");
        if (modal) {
            modal.classList.remove("hidden");
        }
    } else if (isAppStandalone()) {
        if (typeof showToast === 'function') {
            showToast("✅ PPM Organic Farms is already installed as an app on this device!", "success");
        } else {
            alert("PPM Organic Farms is already installed on your device!");
        }
    } else {
        // Fallback for desktop Safari/Firefox or when prompt cannot be shown directly
        if (typeof showToast === 'function') {
            showToast("📲 To install this app, open your browser menu (⋮ or Share) and select 'Install' or 'Add to Home Screen'.", "info");
        } else {
            alert("To install this app, open your browser menu and select 'Install app' or 'Add to Home screen'.");
        }
    }
}

function dismissPwaBanner() {
    const banner = document.getElementById("pwa-install-banner");
    if (banner) {
        banner.classList.add("hidden");
    }
    localStorage.setItem("pwa_banner_dismissed_at", Date.now().toString());
}

function closeIosInstallModal() {
    const modal = document.getElementById("ios-install-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
}

// Wire functions globally
window.initPwaInstaller = initPwaInstaller;
window.triggerPwaInstall = triggerPwaInstall;
window.dismissPwaBanner = dismissPwaBanner;
window.closeIosInstallModal = closeIosInstallModal;



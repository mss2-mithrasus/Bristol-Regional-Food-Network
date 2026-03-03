// Load cart from API and render
async function loadCart() {
    const token = localStorage.getItem('access');
    if (!token) return;

    const res = await fetch('/shopping_cart/api/cart/', {
        headers: { 'Authorization': `Bearer ${token}` }
    });
    const data = await res.json();

    const container = document.getElementById('cart-items');
    if(!container) return; // If not on cart page
    container.innerHTML = '';

    let total = 0;
    data.items.forEach(item => {
        const subtotal = item.unit_price * item.quantity;
        total += subtotal;
        container.innerHTML += `
            <div>
                ${item.product.name} x ${item.quantity} - £${subtotal.toFixed(2)}
                <button onclick="updateCart(${item.id}, 'increase')">+</button>
                <button onclick="updateCart(${item.id}, 'decrease')">-</button>
                <button onclick="removeItem(${item.id})">Remove</button>
            </div>
        `;
    });

    document.getElementById('cart-total').innerText = total.toFixed(2);
}

// Add product to cart
async function addToCart(productId) {
    const token = localStorage.getItem('access');
    if (!token) {
        alert('You must login first!');
        return;
    }

    const res = await fetch(`/shopping_cart/api/cart/add/${productId}/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
    });
    const data = await res.json();
    if(res.ok) alert('Added to cart!');
    else alert('Error: ' + JSON.stringify(data));

    loadCart(); // Refresh cart if on cart page
}

// Update quantity
async function updateCart(itemId, action) {
    const token = localStorage.getItem('access');
    await fetch(`/shopping_cart/api/cart/update/${itemId}/${action}/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    loadCart();
}

// Remove item
async function removeItem(itemId) {
    const token = localStorage.getItem('access');
    await fetch(`/shopping_cart/api/cart/remove/${itemId}/`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
    });
    loadCart();
}

// Attach add-to-cart buttons
document.querySelectorAll('.btn-add-cart').forEach(btn => {
    btn.addEventListener('click', () => {
        const productId = btn.dataset.productId;
        addToCart(productId);
    });
});

// Load cart if cart page
window.addEventListener('DOMContentLoaded', loadCart);
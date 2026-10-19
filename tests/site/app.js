// Tiny client-side "shop" used to test the crawler and the generated Playwright project.
const PRODUCTS = [
  { id: 1, slug: 'backpack', name: 'Trail Backpack', price: 29.99 },
  { id: 2, slug: 'bike-light', name: 'Bike Light', price: 9.99 },
  { id: 3, slug: 'bolt-tshirt', name: 'Bolt T-Shirt', price: 15.99 },
];
const S = window.localStorage;
const cart = () => JSON.parse(S.getItem('cart') || '[]');
const setCart = (c) => { S.setItem('cart', JSON.stringify(c)); renderBadge(); };
function requireLogin() { if (!S.getItem('user')) location.href = 'index.html'; }
function go(url) { location.href = url; }
function renderBadge() {
  const b = document.querySelector('[data-test="shopping-cart-badge"]');
  if (!b) return; const n = cart().length; b.textContent = n; b.style.display = n ? 'inline-block' : 'none';
}
function header() {
  return `<header><button id="react-burger-menu-btn" data-test="open-menu" onclick="document.querySelector('nav').style.display='block';document.querySelector('.overlay').style.display='block'">Open Menu</button>
  <span class="logo">Practice Shop</span>
  <button class="cart" data-test="shopping-cart-link" aria-label="Cart" onclick="go('cart.html')"><span data-test="shopping-cart-badge"></span></button></header>
  <div class="overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.3);z-index:5"
       onclick="this.style.display='none';document.querySelector('nav').style.display='none'"></div>
  <nav style="display:none;position:fixed;top:0;left:0;z-index:6;background:#fff">
    <button data-test="inventory-sidebar-link" onclick="go('inventory.html')">All Items</button>
    <button data-test="orders-sidebar-link" onclick="go('orders.html')">Orders</button>
    <button data-test="logout-sidebar-link" onclick="localStorage.clear(); go('index.html')">Logout</button>
    <button data-test="reset-sidebar-link" onclick="localStorage.removeItem('cart'); renderBadge()">Reset App State</button>
  </nav>`;
}
function addBtn(p) {
  const inCart = cart().includes(p.id);
  return inCart
    ? `<button data-test="remove-${p.slug}" onclick="setCart(cart().filter(x=>x!==${p.id})); location.reload()">Remove</button>`
    : `<button data-test="add-to-cart-${p.slug}" onclick="setCart([...cart(), ${p.id}]); location.reload()">Add to cart</button>`;
}

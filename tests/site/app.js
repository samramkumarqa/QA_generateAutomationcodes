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
  return `<header><button id="react-burger-menu-btn" data-test="open-menu" onclick="document.querySelector('nav').style.display='block'">Open Menu</button>
  <span class="logo">Practice Shop</span>
  <a class="cart" data-test="shopping-cart-link" onclick="go('cart.html')">Cart <span data-test="shopping-cart-badge"></span></a></header>
  <nav style="display:none">
    <a id="inventory_sidebar_link" href="#" onclick="go('inventory.html')">All Items</a>
    <a id="logout_sidebar_link" href="#" onclick="localStorage.clear(); go('index.html')">Logout</a>
    <a id="reset_sidebar_link" href="#" onclick="localStorage.removeItem('cart'); renderBadge()">Reset App State</a>
  </nav>`;
}
function addBtn(p) {
  const inCart = cart().includes(p.id);
  return inCart
    ? `<button data-test="remove-${p.slug}" onclick="setCart(cart().filter(x=>x!==${p.id})); location.reload()">Remove</button>`
    : `<button data-test="add-to-cart-${p.slug}" onclick="setCart([...cart(), ${p.id}]); location.reload()">Add to cart</button>`;
}

-- E-Commerce Database Schema
-- PostgreSQL DDL for creating all tables
-- Run this directly in PostgreSQL if you prefer raw SQL

-- =====================================================
-- Drop existing tables (in reverse dependency order)
-- =====================================================
DROP TABLE IF EXISTS store_followers CASCADE;
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS cart_items CASCADE;
DROP TABLE IF EXISTS video_stories CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS catalogs CASCADE;
DROP TABLE IF EXISTS stores CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TYPE IF EXISTS order_status;

-- =====================================================
-- Create ENUM type for order status
-- =====================================================
CREATE TYPE order_status AS ENUM ('pending', 'paid', 'shipped', 'delivered', 'cancelled');

-- =====================================================
-- Users Table
-- =====================================================
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_phone ON users(phone);

-- =====================================================
-- Stores Table
-- =====================================================
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address VARCHAR(500),
    owner_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stores_owner ON stores(owner_user_id);

-- =====================================================
-- Catalogs Table
-- =====================================================
CREATE TABLE catalogs (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_catalogs_store ON catalogs(store_id);

-- =====================================================
-- Products Table
-- =====================================================
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    catalog_id INTEGER NOT NULL REFERENCES catalogs(id) ON DELETE CASCADE,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10, 2) NOT NULL,
    image_url VARCHAR(500),
    stock_qty INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_products_catalog ON products(catalog_id);
CREATE INDEX idx_products_store ON products(store_id);
CREATE INDEX idx_products_name ON products(name);

-- =====================================================
-- Video Stories Table
-- =====================================================
CREATE TABLE video_stories (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    video_url VARCHAR(500) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_video_stories_store ON video_stories(store_id);
CREATE INDEX idx_video_stories_user ON video_stories(user_id);

-- =====================================================
-- Cart Items Table
-- =====================================================
CREATE TABLE cart_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_cart_user_product UNIQUE (user_id, product_id)
);

CREATE INDEX idx_cart_items_user ON cart_items(user_id);
CREATE INDEX idx_cart_items_product ON cart_items(product_id);

-- =====================================================
-- Orders Table
-- =====================================================
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    total_amount DECIMAL(12, 2) NOT NULL,
    status order_status NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_user ON orders(user_id);
CREATE INDEX idx_orders_store ON orders(store_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created ON orders(created_at);

-- =====================================================
-- Order Items Table
-- =====================================================
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL,
    price_at_purchase DECIMAL(10, 2) NOT NULL
);

CREATE INDEX idx_order_items_order ON order_items(order_id);
CREATE INDEX idx_order_items_product ON order_items(product_id);

-- =====================================================
-- Store Followers Table
-- =====================================================
CREATE TABLE store_followers (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    followed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_follower_user_store UNIQUE (user_id, store_id)
);

CREATE INDEX idx_store_followers_user ON store_followers(user_id);
CREATE INDEX idx_store_followers_store ON store_followers(store_id);

-- =====================================================
-- Useful Views
-- =====================================================

-- View: Store followers with user info (for stores to see their followers)
CREATE OR REPLACE VIEW v_store_followers_info AS
SELECT 
    sf.store_id,
    s.name AS store_name,
    sf.user_id,
    u.name AS follower_name,
    u.phone AS follower_phone,
    sf.followed_at
FROM store_followers sf
JOIN users u ON sf.user_id = u.id
JOIN stores s ON sf.store_id = s.id;

-- View: Store followers with their orders (for stores to see follower purchase history)
CREATE OR REPLACE VIEW v_store_follower_orders AS
SELECT 
    sf.store_id,
    sf.user_id,
    u.name AS customer_name,
    u.phone AS customer_phone,
    o.id AS order_id,
    o.total_amount,
    o.status,
    o.created_at AS order_date
FROM store_followers sf
JOIN users u ON sf.user_id = u.id
LEFT JOIN orders o ON o.user_id = sf.user_id AND o.store_id = sf.store_id;

-- View: Product inventory summary
CREATE OR REPLACE VIEW v_product_inventory AS
SELECT 
    p.id AS product_id,
    p.name AS product_name,
    p.price,
    p.stock_qty,
    c.name AS catalog_name,
    s.name AS store_name,
    s.id AS store_id
FROM products p
JOIN catalogs c ON p.catalog_id = c.id
JOIN stores s ON p.store_id = s.id;

-- =====================================================
-- Grant statements (adjust for your user)
-- =====================================================
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_app_user;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO your_app_user;

COMMENT ON TABLE users IS 'Application users (customers and store owners)';
COMMENT ON TABLE stores IS 'Vendor stores/shops';
COMMENT ON TABLE catalogs IS 'Product catalogs within stores';
COMMENT ON TABLE products IS 'Products available for purchase';
COMMENT ON TABLE video_stories IS 'Video content posted by stores or users';
COMMENT ON TABLE cart_items IS 'Shopping cart items for users';
COMMENT ON TABLE orders IS 'Completed/pending orders';
COMMENT ON TABLE order_items IS 'Individual items within an order';
COMMENT ON TABLE store_followers IS 'User-store follow relationships';

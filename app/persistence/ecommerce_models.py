"""SQLAlchemy models for the e-commerce/store platform."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class OrderStatus(enum.Enum):
    """Enum for order status."""
    pending = "pending"
    paid = "paid"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"


class User(Base):
    """User model for customers and store owners."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    stores: Mapped[List["Store"]] = relationship("Store", back_populates="owner", cascade="all, delete-orphan")
    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="user", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="user", cascade="all, delete-orphan")
    video_stories: Mapped[List["VideoStory"]] = relationship("VideoStory", back_populates="user")
    followed_stores: Mapped[List["StoreFollower"]] = relationship("StoreFollower", back_populates="user", cascade="all, delete-orphan")


class Store(Base):
    """Store model for vendor shops."""
    __tablename__ = "stores"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="stores")
    catalogs: Mapped[List["Catalog"]] = relationship("Catalog", back_populates="store", cascade="all, delete-orphan")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="store", cascade="all, delete-orphan")
    video_stories: Mapped[List["VideoStory"]] = relationship("VideoStory", back_populates="store", cascade="all, delete-orphan")
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="store")
    followers: Mapped[List["StoreFollower"]] = relationship("StoreFollower", back_populates="store", cascade="all, delete-orphan")


class Catalog(Base):
    """Catalog model for organizing products."""
    __tablename__ = "catalogs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="catalogs")
    products: Mapped[List["Product"]] = relationship("Product", back_populates="catalog", cascade="all, delete-orphan")


class Product(Base):
    """Product model for items sold in stores."""
    __tablename__ = "products"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    catalog_id: Mapped[int] = mapped_column(Integer, ForeignKey("catalogs.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    stock_qty: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    catalog: Mapped["Catalog"] = relationship("Catalog", back_populates="products")
    store: Mapped["Store"] = relationship("Store", back_populates="products")
    cart_items: Mapped[List["CartItem"]] = relationship("CartItem", back_populates="product", cascade="all, delete-orphan")
    order_items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="product")


class VideoStory(Base):
    """Video story model for store/user content."""
    __tablename__ = "video_stories"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    video_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    store: Mapped["Store"] = relationship("Store", back_populates="video_stories")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="video_stories")


class CartItem(Base):
    """Cart item model for user shopping carts."""
    __tablename__ = "cart_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="cart_items")
    product: Mapped["Product"] = relationship("Product", back_populates="cart_items")
    
    # Unique constraint: one cart item per user per product
    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="uq_cart_user_product"),
    )


class Order(Base):
    """Order model for completed purchases."""
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    store: Mapped["Store"] = relationship("Store", back_populates="orders")
    items: Mapped[List["OrderItem"]] = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """Order item model for products in an order."""
    __tablename__ = "order_items"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price_at_purchase: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    
    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="items")
    product: Mapped["Product"] = relationship("Product", back_populates="order_items")


class StoreFollower(Base):
    """Store follower model for user-store relationships."""
    __tablename__ = "store_followers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False)
    followed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="followed_stores")
    store: Mapped["Store"] = relationship("Store", back_populates="followers")
    
    # Unique constraint: one follow per user per store
    __table_args__ = (
        UniqueConstraint("user_id", "store_id", name="uq_follower_user_store"),
    )


# Helper function to create all tables
def create_all_tables(database_url: str, echo: bool = False) -> None:
    """Create all tables in the database."""
    engine = create_engine(database_url, echo=echo)
    Base.metadata.create_all(engine)
    print("All tables created successfully!")


def drop_all_tables(database_url: str, echo: bool = False) -> None:
    """Drop all tables from the database."""
    engine = create_engine(database_url, echo=echo)
    Base.metadata.drop_all(engine)
    print("All tables dropped successfully!")

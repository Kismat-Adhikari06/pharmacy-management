"""SQLAlchemy models for the pharmacy management system."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime, Text,
    ForeignKey, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Medicine(Base):
    __tablename__ = "medicines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    medicine_name = Column(String(200), nullable=False)
    generic_name = Column(String(200), nullable=True)
    company = Column(String(200), nullable=True)
    category = Column(String(100), nullable=True)
    med_form = Column(String(50), nullable=True)
    barcode = Column(String(50), nullable=True, unique=True)
    rack_location = Column(String(50), nullable=True)
    minimum_stock = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    batches = relationship("Batch", back_populates="medicine", cascade="all, delete-orphan")


class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True, autoincrement=True)
    medicine_id = Column(Integer, ForeignKey("medicines.id"), nullable=False)
    batch_number = Column(String(100), nullable=False)
    expiry_date = Column(Date, nullable=False)
    purchase_price = Column(Float, nullable=False)
    selling_price = Column(Float, nullable=False)
    quantity = Column(Integer, default=0)
    is_active = Column(Integer, default=1)
    medicine = relationship("Medicine", back_populates="batches")
    purchase_items = relationship("PurchaseItem", back_populates="batch")
    sale_items = relationship("SaleItem", back_populates="batch")


class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_name = Column(String(200), nullable=False)
    contact_person = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(200), nullable=True)
    address = Column(String(500), nullable=True)
    pan_number = Column(String(20), nullable=True, unique=True)
    registration_number = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False, default="Active")
    outstanding_balance = Column(Float, nullable=False, default=0.0)
    last_purchase_date = Column(Date, nullable=True)
    total_purchases = Column(Float, nullable=False, default=0.0)
    purchases = relationship("Purchase", back_populates="supplier")


class Purchase(Base):
    __tablename__ = "purchases"
    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=False)
    invoice_number = Column(String(100), nullable=False)
    purchase_date = Column(Date, nullable=False)
    total_amount = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    supplier = relationship("Supplier", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")


class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    purchase_id = Column(Integer, ForeignKey("purchases.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    purchase_price = Column(Float, nullable=False)
    purchase = relationship("Purchase", back_populates="items")
    batch = relationship("Batch", back_populates="purchase_items")


class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, autoincrement=True)
    bill_number = Column(String(50), unique=True, nullable=False)
    sale_date = Column(DateTime, server_default=func.now())
    total_amount = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)
    vat_amount = Column(Float, default=0.0)
    payment_method = Column(String(20), nullable=False)
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")


class SaleItem(Base):
    __tablename__ = "sale_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    selling_price = Column(Float, nullable=False)
    discount = Column(Float, default=0.0)
    sale = relationship("Sale", back_populates="items")
    batch = relationship("Batch", back_populates="sale_items")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(20), nullable=False)
    full_name = Column(String(100), nullable=True)


class Settings(Base):
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True)
    pharmacy_name = Column(String(200), default="Krisha Pharma")
    address = Column(String(500), default="")
    phone = Column(String(20), default="")
    email = Column(String(200), default="")
    pan_number = Column(String(20), default="")
    registration_number = Column(String(50), default="")
    default_vat = Column(Float, default=13.0)
    receipt_width = Column(String(10), default="80mm")
    currency_symbol = Column(String(10), default="Rs")
    receipt_footer = Column(String(500), default="Thank you for your purchase!")
    auto_print = Column(String(3), default="No")
    enable_expiry_warnings = Column(String(3), default="Yes")
    enable_low_stock_warnings = Column(String(3), default="Yes")
    expiry_warning_days = Column(Integer, default=30)
    default_theme = Column(String(20), default="dark")
    font_size = Column(String(10), default="Medium")
    backup_folder = Column(String(500), default="backups")
    auto_backup_daily = Column(String(3), default="No")
    auto_backup_weekly = Column(String(3), default="No")
    max_backups = Column(Integer, default=10)
    barcode_prefix = Column(String(10), default="PHM")
    scanner_suffix = Column(String(10), default="")
    auto_add_after_scan = Column(String(3), default="Yes")
    play_success_sound = Column(String(3), default="No")
    play_error_sound = Column(String(3), default="No")
    barcode_label_width = Column(String(20), default="50x30mm")
    barcode_label_font_size = Column(Integer, default=8)
    openrouter_api_key = Column(String(500), nullable=True, default="")

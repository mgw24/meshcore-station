from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Float, Boolean, JSON, Index
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from station.config import DB_URL

class Base(DeclarativeBase): pass

def utcnow(): return datetime.now(timezone.utc)

class Contact(Base):
    __tablename__ = 'contacts'
    public_key = Column(String(130), primary_key=True)
    name = Column(String(200), nullable=False, default='Unknown')
    role = Column(String(80), default='unknown')
    first_seen = Column(DateTime(timezone=True), default=utcnow)
    last_seen = Column(DateTime(timezone=True), default=utcnow)
    detail = Column(JSON, default=dict)

class NodeLocation(Base):
    __tablename__ = 'node_locations'
    public_key = Column(String(130), primary_key=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    updated = Column(DateTime(timezone=True), default=utcnow)

class AddressEntry(Base):
    """Local address book; independent of the radio-discovered contact list."""
    __tablename__ = 'address_book'
    id = Column(Integer, primary_key=True)
    public_key = Column(String(130), unique=True, nullable=True, index=True)
    nickname = Column(String(100), nullable=False)
    notes = Column(Text, nullable=False, default='')
    tags = Column(String(240), nullable=False, default='')
    favorite = Column(Boolean, nullable=False, default=False)
    updated = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class RxActivity(Base):
    """Decoded RX metadata or an explicitly labelled packet-counter delta."""
    __tablename__ = 'rx_activity'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    kind = Column(String(48), nullable=False)
    summary = Column(String(200), nullable=False)
    source = Column(String(130), nullable=False, default='')
    channel = Column(Integer, nullable=True)
    rssi = Column(Float, nullable=True)
    snr = Column(Float, nullable=True)
    count = Column(Integer, nullable=False, default=1)
    errors = Column(Integer, nullable=False, default=0)
    detail = Column(JSON, default=dict)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    direction = Column(String(8), nullable=False)
    kind = Column(String(12), nullable=False)
    target = Column(String(130), nullable=False, default='')
    sender = Column(String(130), nullable=False, default='')
    body = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default='received')
    meta = Column(JSON, default=dict)

class RadioEvent(Base):
    __tablename__ = 'radio_events'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    kind = Column(String(90), nullable=False)
    detail = Column(JSON, default=dict)

class Sample(Base):
    __tablename__ = 'samples'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    battery_pct = Column(Float, nullable=True)
    noise_floor = Column(Float, nullable=True)
    uptime = Column(Float, nullable=True)
    rssi = Column(Float, nullable=True)
    snr = Column(Float, nullable=True)
    packets_rx = Column(Float, nullable=True)
    packets_tx = Column(Float, nullable=True)
    stats = Column(JSON, default=dict)

class Alert(Base):
    __tablename__ = 'alerts'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    severity = Column(String(20), nullable=False)
    message = Column(String(400), nullable=False)
    resolved = Column(Boolean, default=False)

class Command(Base):
    __tablename__ = 'commands'
    id = Column(Integer, primary_key=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    kind = Column(String(24), nullable=False)
    args = Column(JSON, default=dict)
    state = Column(String(24), default='pending', index=True)
    error = Column(Text, default='')
    result = Column(JSON, default=dict)
    finished = Column(DateTime(timezone=True), nullable=True)

class StationStatus(Base):
    __tablename__ = 'station_status'
    key = Column(String(80), primary_key=True)
    value = Column(JSON, default=dict)
    updated = Column(DateTime(timezone=True), default=utcnow)

Index('ix_messages_target_ts', Message.target, Message.ts)
engine = create_engine(DB_URL, pool_pre_ping=True, pool_recycle=1800)
Session = sessionmaker(bind=engine, expire_on_commit=False)

def initialize(): Base.metadata.create_all(engine)

def record_event(kind, detail=None):
    with Session.begin() as db:
        db.add(RadioEvent(kind=kind, detail=detail or {}))

def status_set(key, value):
    with Session.begin() as db:
        row = db.get(StationStatus, key)
        if row:
            row.value = value
            row.updated = utcnow()
        else:
            db.add(StationStatus(key=key, value=value))

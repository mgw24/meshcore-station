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

class TxEvidence(Base):
    """Persistent evidence associated with a specific outbound message."""
    __tablename__ = 'tx_evidence'
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False, index=True)
    ts = Column(DateTime(timezone=True), default=utcnow, index=True)
    kind = Column(String(40), nullable=False)  # radio_accepted | direct_ack | channel_echo
    detail = Column(JSON, default=dict)

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

class DigestSettings(Base):
    """Single-station email digest configuration. SMTP password is Fernet-encrypted."""
    __tablename__ = 'digest_settings'
    id = Column(Integer, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    frequency = Column(String(20), nullable=False, default='daily')
    send_time = Column(String(5), nullable=False, default='08:00')
    weekday = Column(Integer, nullable=False, default=0)
    timezone = Column(String(80), nullable=False, default='America/Los_Angeles')
    include_received = Column(Boolean, nullable=False, default=True)
    include_sent = Column(Boolean, nullable=False, default=False)
    include_radio = Column(Boolean, nullable=False, default=True)
    include_alerts = Column(Boolean, nullable=False, default=True)
    include_nodes = Column(Boolean, nullable=False, default=True)
    include_rx = Column(Boolean, nullable=False, default=False)
    message_limit = Column(Integer, nullable=False, default=100)
    smtp_host = Column(String(255), nullable=False, default='')
    smtp_port = Column(Integer, nullable=False, default=587)
    smtp_security = Column(String(12), nullable=False, default='starttls')
    smtp_username = Column(String(255), nullable=False, default='')
    smtp_password_enc = Column(Text, nullable=False, default='')
    mail_from = Column(String(255), nullable=False, default='')
    mail_to = Column(Text, nullable=False, default='')
    schedule_anchor = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

class DigestDelivery(Base):
    """Durable queue/history, unique scheduled slot prevents duplicate automatic sends."""
    __tablename__ = 'digest_deliveries'
    id = Column(Integer, primary_key=True)
    slot_key = Column(String(90), unique=True, nullable=True)
    kind = Column(String(16), nullable=False)  # scheduled | manual | test | probe
    status = Column(String(20), nullable=False, default='queued')
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    recipient_count = Column(Integer, nullable=False, default=0)
    message_count = Column(Integer, nullable=False, default=0)
    error = Column(String(400), nullable=False, default='')

import asyncio
from station.db import initialize, Session, Contact, Message, Command
from station.worker import Collector, jsonsafe


def test_jsonsafe_bytes():
    assert jsonsafe({b'\xaa': [b'\xbb']}) == {'aa': ['bb']}


def test_simulated_message():
    initialize()
    async def exercise():
        worker=Collector()
        await worker.connect()
        with Session.begin() as db:
            cmd=Command(kind='send', args={'kind':'channel','destination':'0','text':'hello simulation'})
            db.add(cmd)
            db.flush()
            id_=cmd.id
        for _ in range(10):
            assert await worker.drain_commands()
            with Session() as db:
                if db.get(Command,id_).state=='complete': break
        with Session() as db:
            assert db.get(Command,id_).state=='complete'
            assert db.query(Message).filter(Message.body=='hello simulation').first().status=='simulated'
        await worker.close()
    asyncio.run(exercise())

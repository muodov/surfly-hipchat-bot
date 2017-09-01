from peewee import (
    Model,
    IntegerField,
    CharField,
)
from playhouse.db_url import connect

from settings import DATABASE_URL


if DATABASE_URL:
    db = connect(DATABASE_URL)
else:
    db = None


class BaseModel(Model):
    class Meta:
        database = db


class Installation(BaseModel):
    oauth_id = CharField(unique=True)
    oauth_secret = CharField()
    capabilities_url = CharField()
    room_id = IntegerField(null=True)
    group_id = IntegerField(null=True)


if __name__ == '__main__':
    db.connect()
    db.create_tables([Installation], safe=True)
    db.close()

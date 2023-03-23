from datetime import date, datetime, timedelta, timezone

#from pytz import timezone

datetime_utc = datetime.utcnow()
datetime_kst = datetime_utc + timedelta(hours=9)
today = datetime_kst.today().date().strftime('%Y.%m.%d')
#today = datetime.now(timezone('Asia/Seoul'))
print(datetime_utc)
print(datetime_kst)
print(today)
#print(datetime_utc + timedelta(hours=19))
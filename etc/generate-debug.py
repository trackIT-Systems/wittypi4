import datetime
import yaml


start = datetime.datetime(2024, 1, 1, 0, 0, 0)
end = datetime.datetime(2024, 1, 2, 0, 0, 0)
on_dt = datetime.timedelta(minutes=4)
off_dt = datetime.timedelta(minutes=1)

schedule = []
ts = start
i = 0
while ts < end:
    entry = dict(
        name=f"debug_{i}",
        start=ts.strftime("%H:%M"),
    )
    i += 1
    ts += on_dt
    entry.update(dict(
        stop=ts.strftime("%H:%M"),
    ))
    ts += off_dt

    schedule.append(entry)


config = dict(
    lat=50.85318,
    lon=8.78735,
    force_on=False,
    button_delay="00:30",
    schedule=schedule,
)

print(yaml.dump(config))

# nasa-daily-cosmos

A daily glimpse of the cosmos: NASA's picture of the day as a small notification.

Each morning you get a photo, its title and a few lines about it. Curious? Click **Details** to read the
full story. Liked it? Add it to your favorites, or set it as your wallpaper. Works on Linux (GNOME)
and Windows. Pure Python standard library, nothing to `pip install`.

- **Today's picture** comes from [APOD](https://apod.nasa.gov/). On video days, or while the APOD API is
  broken, it falls back to [NASA Image of the Day](https://www.nasa.gov/image-of-the-day/).
- **Random** shows a random space photo from the [NASA Image Library](https://images.nasa.gov/).
- Pictures are saved to `~/Pictures/NasaPhotos` and deleted after 7 days. Favorites are kept forever in
  `~/Pictures/NasaPhotos/favorites`; open `favorites/index.html` there to browse them with their full
  explanations.

## Usage

```sh
python3 nasa_daily_cosmos.py            # show today's picture
python3 nasa_daily_cosmos.py random     # show a random NASA photo
python3 nasa_daily_cosmos.py favorite   # save the last shown picture to favorites
```

Optionally get a free API key from [api.nasa.gov](https://api.nasa.gov/) and set it as `NASA_API_KEY`.
Without one the shared `DEMO_KEY` is used, which is enough for daily use.

Buttons and messages follow the system language (English or Turkish). Set `NASA_DAILY_COSMOS_LANG=tr` or
`NASA_DAILY_COSMOS_LANG=en` to override it.

Tests: `python3 -m unittest`.

## Run daily on Linux (GNOME)

```sh
install -Dm755 nasa_daily_cosmos.py ~/.local/bin/nasa-daily-cosmos
install -Dm644 -t ~/.config/systemd/user systemd/nasa-daily-cosmos.service systemd/nasa-daily-cosmos.timer
echo "NASA_API_KEY=your-key" >> ~/.config/nasa-daily-cosmos.env   # optional
echo "NASA_DAILY_COSMOS_LANG=tr" >> ~/.config/nasa-daily-cosmos.env  # optional
systemctl --user daemon-reload
systemctl --user enable --now nasa-daily-cosmos.timer
```

It runs every day at 09:00, or right after login if the computer was off. To run it now:
`systemctl --user start nasa-daily-cosmos`.

## Run daily on Windows

Install Python from [python.org](https://www.python.org/downloads/) (it includes the Tk library the
popup window needs). Then in PowerShell, from this folder:

```powershell
$action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "`"$PWD\nasa_daily_cosmos.py`""
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "NASA Daily Cosmos" -Action $action -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` runs it after login if the computer was off at 09:00.

# nasa-daily-wallpaper

Every day, shows NASA's picture of the day in a notification, with buttons to set it as your wallpaper,
save it to favorites or read more about it. Works on Linux (GNOME) and Windows. Pure Python standard
library, nothing to `pip install`.

- **Today's picture** comes from [APOD](https://apod.nasa.gov/). On video days, or while the APOD API is
  broken, it falls back to [NASA Image of the Day](https://www.nasa.gov/image-of-the-day/).
- **Skip** sets a random wallpaper-sized space photo from the [NASA Image Library](https://images.nasa.gov/).
- Pictures are saved to `~/Pictures/NasaPhotos`, favorites to `~/Pictures/NasaPhotos/favorites`.

## Usage

```sh
python3 nasa_wallpaper.py            # offer today's picture
python3 nasa_wallpaper.py --auto     # set today's picture without asking
python3 nasa_wallpaper.py skip       # random NASA photo as wallpaper
python3 nasa_wallpaper.py favorite   # save the current wallpaper to favorites
```

Optionally get a free API key from [api.nasa.gov](https://api.nasa.gov/) and set it as `NASA_API_KEY`.
Without one the shared `DEMO_KEY` is used, which is enough for daily use.

Buttons and messages follow the system language (English or Turkish). Set `NASA_WALLPAPER_LANG=tr` or
`NASA_WALLPAPER_LANG=en` to override it.

## Run daily on Linux (GNOME)

```sh
install -Dm755 nasa_wallpaper.py ~/.local/bin/nasa-wallpaper
install -Dm644 -t ~/.config/systemd/user systemd/nasa-wallpaper.service systemd/nasa-wallpaper.timer
echo "NASA_API_KEY=your-key" >> ~/.config/nasa-wallpaper.env   # optional
echo "NASA_WALLPAPER_LANG=tr" >> ~/.config/nasa-wallpaper.env  # optional
systemctl --user daemon-reload
systemctl --user enable --now nasa-wallpaper.timer
```

It runs every day at 09:00, or right after login if the computer was off. To run it now:
`systemctl --user start nasa-wallpaper`.

## Run daily on Windows

Install Python from [python.org](https://www.python.org/downloads/) (it includes the Tk library the
popup window needs). Then in PowerShell, from this folder:

```powershell
$action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "`"$PWD\nasa_wallpaper.py`""
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
Register-ScheduledTask -TaskName "NASA Wallpaper" -Action $action -Trigger $trigger -Settings $settings
```

`-StartWhenAvailable` runs it after login if the computer was off at 09:00.

# Smart Campus — Public deployment

## Render
- Runtime: Python 3.12.10
- Build: `pip install -r requirements.txt`
- Start: `gunicorn run:app --workers 1 --threads 4 --timeout 180`
- Required environment variables: `SECRET_KEY`, `DATABASE_URL`

For a first public test, a Render web service can provide an HTTPS `onrender.com` URL. The free web service can sleep after inactivity, so it is not intended as the final college production setup.

## Production data
The current app can use PostgreSQL through `DATABASE_URL`. For the final college deployment, use persistent PostgreSQL and persistent document storage; the local filesystem used by the development document upload route should not be treated as permanent cloud storage.

## Mobile
The templates already include the viewport meta tag and responsive CSS. The public HTTPS URL can be opened in Chrome on Android/iPhone. Camera and geolocation require browser permission and HTTPS in production.

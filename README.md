MOTOFIX Auth Service

This service handles OTP-based authentication for MOTOFIX.

Quick setup (development)

1. Create a virtual environment and activate it:

```powershell
python -m venv venv
& .\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and fill in credentials (optional):

```powershell
copy .env.example .env
# then edit .env to add your AT_USERNAME and AT_API_KEY
```

4. Run the app:

```powershell
uvicorn app.main:app --reload
```

Africa's Talking (OTP SMS)

- To enable sending OTPs via Africa's Talking, set the following environment variables (or put them into `.env`):

```
AT_USERNAME=your_africas_talking_username
AT_API_KEY=your_africas_talking_api_key
AT_FROM=+1234567890  # optional
```

- The app falls back to printing the OTP to the server console if the SDK or credentials are not present.

Security notes

- OTPs are kept in an in-memory store for development. For production, consider using Redis with expiry and rate limiting.
- Do not commit real credentials to source control.

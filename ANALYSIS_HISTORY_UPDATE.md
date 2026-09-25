# Analysis History Update

Implemented:
- Every authenticated chart analysis is stored and shared with other authenticated users.
- History scopes: `mine`, `other`, and `all`.
- Analyst name/email and `is_mine` are returned with every history item.
- A notification is created for every other registered user when a new analysis is published.
- Notification endpoints: list, mark read, unread count.
- PDF endpoint: `GET /analyzer/history/{analysis_id}/pdf`.
- PDF includes analyst, date, coin, market read, scenarios and disclaimer.
- `reportlab` added to requirements.

No database migration script is required for the existing schema because the backend already calls `Base.metadata.create_all()` at startup; the new `analysis_notifications` table is created automatically.

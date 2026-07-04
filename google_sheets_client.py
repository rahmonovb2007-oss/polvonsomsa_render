import os
import logging
# pyrefly: ignore [missing-import]
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def get_sheets_service(credentials_path):
    """
    Authenticate and get Google Sheets API service.
    """
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f"Google credentials file not found at: {credentials_path}")
    
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=scopes
    )
    service = build("sheets", "v4", credentials=creds)
    return service

def sync_tandoor_to_sheets(config, tandoor_record, somsa_names):
    """
    Syncs a single tandoor record to the Google Sheet.
    Returns: (success_bool, message_str)
    """
    gs_config = config.get("google_sheets", {})
    if not gs_config.get("enabled", False):
        return False, "Google Sheets sync is disabled in config."
    
    spreadsheet_id = gs_config.get("spreadsheet_id")
    if not spreadsheet_id:
        return False, "Google Spreadsheet ID is not configured."
        
    credentials_file = gs_config.get("credentials_file", "google_credentials.json")
    # Resolve relative path to main.py directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.join(base_dir, credentials_file)
    
    sheet_name = gs_config.get("sheet_name", "Tandir Hisoboti")
    
    try:
        service = get_sheets_service(credentials_path)
        sheet_api = service.spreadsheets()
        
        # 1. Check if sheet tab exists
        spreadsheet = sheet_api.get(spreadsheetId=spreadsheet_id).execute()
        sheets = spreadsheet.get("sheets", [])
        sheet_exists = any(s.get("properties", {}).get("title") == sheet_name for s in sheets)
        
        # 2. If it does not exist, create it
        if not sheet_exists:
            body = {
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": sheet_name
                            }
                        }
                    }
                ]
            }
            sheet_api.batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
            logger.info(f"Created new sheet tab '{sheet_name}' in Google Spreadsheet.")
            
            # Write headers
            headers = [
                "Vaqt",
                "Sana",
                "Tandir nomi",
                f"5 000 ({somsa_names.get('5000', 'Kartoshka')})",
                f"8 000 ({somsa_names.get('8000', 'Mol oʻrta')})",
                f"10 000 ({somsa_names.get('10000', 'Mol katta')})",
                f"15 000 ({somsa_names.get('15000', 'Qoʻy oʻrta')})",
                f"20 000 ({somsa_names.get('20000', 'Qoʻy katta')})",
                f"25 000 ({somsa_names.get('25000', 'Polvon')})",
                "Jami somsa (ta)",
                "Jami pul (SO'M)",
                "Kiritdi"
            ]
            
            sheet_api.values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A1",
                valueInputOption="USER_ENTERED",
                body={"values": [headers]}
            ).execute()
            
        # 3. Format row data
        import datetime
        timestamp_sec = tandoor_record.get("timestamp", 0) / 1000.0
        time_str = datetime.datetime.fromtimestamp(timestamp_sec).strftime("%H:%M:%S")
        date_str = tandoor_record.get("date", "")
        tandoor_name = tandoor_record.get("tandoor_name", "")
        counts = tandoor_record.get("counts", {})
        totals = tandoor_record.get("totals", {})
        creator = tandoor_record.get("creator_name", "Noma'lum")
        
        row_values = [
            time_str,
            date_str,
            tandoor_name,
            counts.get("5000", 0),
            counts.get("8000", 0),
            counts.get("10000", 0),
            counts.get("15000", 0),
            counts.get("20000", 0),
            counts.get("25000", 0),
            totals.get("count", 0),
            totals.get("revenue", 0),
            creator
        ]
        
        # 4. Append row to spreadsheet
        sheet_api.values().append(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [row_values]}
        ).execute()
        
        return True, "Successfully synced to Google Sheets."
        
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Failed to sync tandoor to Google Sheets: {err_msg}")
        return False, err_msg

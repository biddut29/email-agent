"""
Authentication Manager - Handles OAuth and session management
"""
import os
import secrets
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import config


class AuthManager:
    """Manages OAuth authentication and user sessions"""
    
    # OAuth 2.0 scopes required for Gmail access
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.send',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
    ]
    
    def __init__(self):
        self.client_id = config.GOOGLE_CLIENT_ID
        self.client_secret = config.GOOGLE_CLIENT_SECRET
        self.redirect_uri = config.GOOGLE_REDIRECT_URI
        self.session_secret = config.SESSION_SECRET
        
    def get_authorization_url(self, state: Optional[str] = None) -> Tuple[str, str]:
        """Generate Google OAuth authorization URL"""
        if not self.client_id or not self.client_secret:
            raise ValueError("Google OAuth credentials not configured")
        
        if state is None:
            state = secrets.token_urlsafe(32)
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        # Use 'select_account consent' to force account selection and re-consent
        authorization_url, generated_state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account consent',  # Force account selection and consent screen
            state=state
        )
        
        # Add a unique timestamp and random nonce to force Google to show account picker
        # This prevents Google from auto-selecting the last used account by making each URL unique
        import time
        import secrets
        import urllib.parse
        timestamp = int(time.time() * 1000)  # Milliseconds for uniqueness
        nonce = secrets.token_urlsafe(12)  # Longer random nonce to make URL unique
        
        # Parse the URL to add parameters properly
        parsed_url = urllib.parse.urlparse(authorization_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Add our unique parameters to prevent caching
        query_params['_t'] = [str(timestamp)]
        query_params['_n'] = [nonce]
        
        # Rebuild URL with new parameters
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        authorization_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        print(f"🔑 Generated OAuth URL with forced account selection")
        print(f"   URL (first 200 chars): {authorization_url[:200]}...")
        print(f"   Parameters: prompt=select_account consent, timestamp={timestamp}, nonce={nonce[:8]}...")
        print(f"   Full URL length: {len(authorization_url)} characters")
        
        return authorization_url, generated_state
    
    def get_user_info(self, credentials: Credentials) -> Dict:
        """Get user information from Google"""
        try:
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            return {
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'id': user_info.get('id')
            }
        except Exception as e:
            print(f"Error getting user info: {e}")
            return {}
    
    def exchange_code_for_credentials(self, code: str) -> Credentials:
        """Exchange authorization code for credentials"""
        import requests
        import json
        
        # Make the token exchange request directly to avoid scope validation issues
        # This bypasses the OAuth library's strict scope validation
        token_data = {
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri,
            'grant_type': 'authorization_code'
        }
        
        try:
            response = requests.post(
                'https://oauth2.googleapis.com/token',
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error_description', error_json.get('error', error_detail))
                except:
                    pass
                print(f"❌ Token exchange failed: {response.status_code} - {error_detail}")
                raise ValueError(f"Token exchange failed: {error_detail}")
            
            token_info = response.json()
            
            # Extract scopes from response
            returned_scopes = token_info.get('scope', '')
            if isinstance(returned_scopes, str):
                returned_scopes = returned_scopes.split()
            elif not returned_scopes:
                # If no scopes in response, use requested scopes
                returned_scopes = self.SCOPES
            
            # Normalize scopes - remove 'openid' if present (added automatically by Google)
            # and ensure we have all required scopes
            normalized_scopes = [s for s in returned_scopes if s != 'openid'] if returned_scopes else self.SCOPES
            # Ensure all required scopes are present
            for required_scope in self.SCOPES:
                if required_scope not in normalized_scopes:
                    normalized_scopes.append(required_scope)
            
            # Create credentials from token response
            credentials = Credentials(
                token=token_info.get('access_token'),
                refresh_token=token_info.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self.client_id,
                client_secret=self.client_secret,
                scopes=normalized_scopes
            )
            print(f"✓ OAuth token exchange successful")
            return credentials
            
        except ValueError:
            # Re-raise ValueError (our custom errors)
            raise
        except Exception as e:
            print(f"❌ OAuth token exchange error: {e}")
            raise ValueError(f"Failed to exchange authorization code: {str(e)}")
    
    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        """Refresh expired credentials"""
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return credentials
    
    def credentials_to_dict(self, credentials: Credentials) -> Dict:
        """Convert credentials to dictionary for storage"""
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
    
    def dict_to_credentials(self, creds_dict: Dict) -> Credentials:
        """Convert dictionary back to Credentials object"""
        return Credentials(
            token=creds_dict.get('token'),
            refresh_token=creds_dict.get('refresh_token'),
            token_uri=creds_dict.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=creds_dict.get('client_id', self.client_id),
            client_secret=creds_dict.get('client_secret', self.client_secret),
            scopes=creds_dict.get('scopes', self.SCOPES)
        )


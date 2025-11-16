# 📎 Attachment Storage System - Hybrid Approach

## Implementation Summary

The attachment storage system uses a **hybrid approach** combining filesystem storage for binary files with MongoDB metadata storage.

## Architecture

### Storage Structure
```
Backend/attachments/
├── account_1/
│   ├── msg_abc123_photo.jpg
│   ├── msg_abc123_invoice.pdf
│   └── msg_xyz789_document.docx
└── account_2/
    ├── msg_def456_image.png
    └── msg_def456_report.xlsx
```

### Filename Format
- **Pattern**: `msg_{sanitized_message_id}_{sanitized_filename}`
- **Uniqueness**: Numeric suffixes added automatically if duplicates exist
- **Example**: `msg_abc123_photo.jpg` → `msg_abc123_photo_1.jpg` (if duplicate)

### MongoDB Storage
Stores **metadata only** (no binary data):
```json
{
  "message_id": "abc123",
  "account_id": 2,
  "subject": "Invoice",
  "attachments": [
    {
      "original_filename": "invoice.pdf",
      "saved_filename": "msg_abc123_invoice.pdf",
      "content_type": "application/pdf",
      "size": 245760,
      "file_path": "account_2/msg_abc123_invoice.pdf",
      "hash": "sha256_hash_here",
      "storage": "filesystem"
    }
  ]
}
```

## API Endpoints

### 1. List Attachments
```http
GET /api/emails/{message_id}/attachments
```
**Response**: Array of attachment metadata

### 2. Get Attachment (Base64)
```http
GET /api/emails/{message_id}/attachments/{saved_filename}
```
**Response**: Base64-encoded file data + metadata
**Use for**: Displaying images/PDFs in UI

### 3. Download Attachment
```http
GET /api/emails/{message_id}/attachments/{saved_filename}/download
```
**Response**: Raw binary file (triggers browser download)
**Use for**: File downloads

### 4. Storage Statistics
```http
GET /api/storage/stats
```
**Response**: Total files, sizes per account

## Frontend Integration

### API Client Methods (`Frontend/lib/api.ts`)
```typescript
// List all attachments for an email
await api.listAttachments(messageId);

// Get attachment as base64 (for display)
await api.getAttachment(messageId, savedFilename);

// Download attachment (opens in new tab)
await api.downloadAttachment(messageId, savedFilename);

// Get storage statistics
await api.getStorageStats();
```

### Usage Example
```typescript
// In EmailDashboard component
const attachments = await api.listAttachments(email.message_id);

attachments.attachments.forEach(att => {
  if (att.content_type.startsWith('image/')) {
    // Display inline
    const data = await api.getAttachment(email.message_id, att.saved_filename);
    // Show: <img src={`data:${data.content_type};base64,${data.data}`} />
  } else {
    // Show download link
    // On click: api.downloadAttachment(email.message_id, att.saved_filename)
  }
});
```

## Key Features

### ✅ Benefits
1. **Fast Access**: Direct filesystem reads (no database overhead)
2. **Organized**: Account-level folders prevent cross-contamination
3. **Unique Names**: Automatic suffix handling prevents overwrites
4. **Secure**: Message ID prefix prevents filename collisions
5. **Scalable**: File hashes for deduplication (future optimization)
6. **Cleanup**: Account deletion removes all associated files

### 🔒 Security
- Filenames sanitized (no `../`, `/`, `\`, null bytes)
- Message IDs sanitized (no angle brackets, @ symbols)
- Account isolation (each account has own folder)
- Authentication required for all attachment endpoints

### 🧹 Cleanup
- **Per Account**: `attachment_storage.delete_account_attachments(account_id)`
- **Per Email**: `attachment_storage.delete_email_attachments(account_id, message_id)`
- **Per File**: `attachment_storage.delete_attachment(account_id, message_id, saved_filename)`

## Files Modified

### Backend
1. **`Backend/attachment_storage.py`** (NEW)
   - `AttachmentStorage` class
   - Save, retrieve, delete operations
   - Filename sanitization and uniqueness handling

2. **`Backend/api_server.py`**
   - Added imports: `base64`, `mimetypes`, `attachment_storage`, `Response`
   - 4 new endpoints: list, get, download, stats
   - Account deletion updated to clean up attachments

3. **`Backend/mongodb_manager.py`**
   - `save_emails()` updated to process attachments
   - Binary data saved to filesystem
   - Only metadata stored in MongoDB

### Frontend
4. **`Frontend/lib/api.ts`**
   - 4 new methods: `listAttachments`, `getAttachment`, `downloadAttachment`, `getStorageStats`

## Testing Locally

### 1. Check Attachments Folder
```bash
ls -la Backend/attachments/
```

### 2. Send Email with Attachment
Use the UI or API to load an email with attachments

### 3. Verify File Saved
```bash
ls -la Backend/attachments/account_*/
```

### 4. Check Storage Stats
```bash
curl http://localhost:8000/api/storage/stats
```

### Expected Output
```json
{
  "success": true,
  "total_files": 3,
  "total_size_bytes": 1048576,
  "total_size_mb": 1.0,
  "total_size_gb": 0.001,
  "storage_path": "/path/to/Backend/attachments",
  "accounts": {
    "account_1": {
      "files": 2,
      "size": 524288,
      "size_mb": 0.5
    },
    "account_2": {
      "files": 1,
      "size": 524288,
      "size_mb": 0.5
    }
  }
}
```

## Next Steps

### Frontend UI Components (To Be Implemented)
1. **Attachment List Component** - Show all attachments for an email
2. **Image Viewer** - Inline display of image attachments
3. **PDF Viewer** - Embedded PDF viewing
4. **Download Button** - Trigger file downloads

### Future Enhancements
1. **Deduplication**: Use file hashes to avoid storing duplicates
2. **Compression**: Compress large attachments
3. **Thumbnails**: Generate thumbnails for images
4. **OCR/Vision AI**: Extract text from images/PDFs for vector search
5. **Cloud Storage**: Optional S3/Azure Blob integration

## Status

✅ Backend implementation complete
✅ API endpoints ready
✅ Frontend API client ready
🔲 UI components (pending)
🔲 Cloud deployment configuration (pending)

---

**Implementation Date**: November 15, 2024  
**Version**: 1.0.0  
**Approach**: Hybrid (Filesystem + MongoDB Metadata)



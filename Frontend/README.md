# Email Agent - Frontend

Modern Next.js 15 dashboard with Shadcn UI for the Email Agent system.

## Features

- 📧 **Email Inbox**: View and manage emails with a beautiful interface
- 🤖 **AI Analysis**: Real-time AI-powered email categorization and insights
- ✍️ **Smart Replies**: Generate AI responses with one click
- 🔍 **Search**: Powerful email search functionality
- 📊 **Statistics**: Visual analytics and email insights
- 🎨 **Modern UI**: Built with Shadcn UI components and Tailwind CSS
- 🌙 **Dark Mode**: Full dark mode support

## Tech Stack

- **Framework**: Next.js 15 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS v4
- **UI Components**: Shadcn UI
- **Icons**: Lucide React
- **API Client**: Custom fetch-based API wrapper

## Setup

### 1. Install Dependencies

```bash
cd Frontend
npm install
```

### 2. Configure Environment

Create/edit `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The app will be available at [http://localhost:3000](http://localhost:3000)

## Project Structure

```
Frontend/
├── app/
│   ├── layout.tsx          # Root layout
│   ├── page.tsx            # Home page
│   └── globals.css         # Global styles
├── components/
│   ├── ui/                 # Shadcn UI components
│   └── EmailDashboard.tsx  # Main dashboard component
├── lib/
│   ├── api.ts             # API client
│   └── utils.ts           # Utility functions
└── public/                # Static assets
```

## Available Features

### 1. Inbox View
- View all emails in a clean, organized list
- Click any email to see full details
- See AI analysis badges (category, urgency)
- View attachments count

### 2. Email Details
- Read full email content
- View sender, recipient, date
- See AI-powered analysis:
  - Category classification
  - Urgency detection
  - Email summary
  - Action items

### 3. AI Response Generation
- Click "Generate AI Response" button
- AI creates contextual reply based on email content
- Edit the response before sending
- One-click send

### 4. Search
- Search emails by keywords
- Filter by sender
- Filter by subject
- Real-time results

### 5. Statistics Dashboard
- Total emails processed
- Emails with attachments
- Average urgency score
- Spam detection count
- Category breakdown chart

## API Integration

The frontend communicates with the Python backend API running on port 8000.

### Key API Endpoints Used:

- `GET /api/emails` - Fetch emails
- `GET /api/emails/unread` - Fetch unread emails
- `POST /api/emails/send` - Send new email
- `POST /api/emails/reply` - Reply to email
- `POST /api/emails/analyze` - AI analysis
- `POST /api/emails/generate-response` - Generate AI reply
- `POST /api/emails/search` - Search emails
- `GET /api/statistics` - Get statistics

## Customization

### Styling

Edit `app/globals.css` to customize the theme:

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    /* ... more CSS variables */
  }
}
```

### Adding Components

Add new Shadcn components:

```bash
npx shadcn@latest add [component-name]
```

Available components: dialog, dropdown-menu, form, label, popover, sheet, toast, etc.

## Building for Production

```bash
npm run build
npm run start
```

## Development Tips

### Hot Reload
Changes to components auto-refresh in the browser.

### TypeScript
The project uses strict TypeScript. Check types with:

```bash
npm run build
```

### Linting
```bash
npm run lint
```

## Troubleshooting

### API Connection Issues
- Ensure backend server is running on port 8000
- Check `.env.local` has correct API URL
- Verify CORS is enabled in backend

### Component Not Found
- Install Shadcn component: `npx shadcn@latest add [component]`
- Check import path uses `@/` alias

### Build Errors
- Clear `.next` folder: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

MIT License

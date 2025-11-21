# Quick UI Reference - Streamlit E2E OpenAI App

## 🎯 Key UI Sections

### 1. **Header Section**
```
🤖 Loss Run Processing System (OpenAI)
[Centered, Large Blue Text]
```

### 2. **Step 1: Upload PDF**
- File uploader widget
- 3 metric cards showing:
  - File Name: `sample.pdf`
  - File Size: `1,234.5 KB`
  - Upload Time: `14:32:15`
- Green success box: `[SUCCESS] File uploaded to backup successfully!`

### 3. **Step 2: Process File**
- ☑️ Debug Mode checkbox (default: ON)
- 🚀 Start Processing button (primary, blue)
- Progress bar (0-100%)
- Status text updates
- **Debug Logs Section** (when enabled):
  - Code block with real-time output
  - Prefixed with `[PDF->Text]` or `[OpenAI]`
  - Scrollable text area

### 4. **Step 3: Results & Summary**

#### ⏱️ Processing Times Table
```
Step                 | Formatted
─────────────────────|──────────────────────
PDF to Text          | 3.45 seconds
OpenAI Extraction    | 1 minute 23.12 seconds
Total Time           | 1 minute 26.57 seconds
```

#### 📊 Summary Section (Expandable)
- **4 Metric Cards** (side by side):
  ```
  AUTO:      $125,450.00 | Claims: 15 | Avg: $8,363
  PROPERTY:  $0.00       | Claims: 0  | Avg: $0
  GL:        $89,230.00  | Claims: 8   | Avg: $11,154
  WC:        $0.00       | Claims: 0  | Avg: $0
  ```

- **Charts**:
  - Top 10 Claims by Loss (Bar Chart) - per LOB
  - LOB-wise Total Loss (Pie Chart)
  - LOB-wise ALAE (Bar Chart)

#### 📄 Data Tables (Expandable Sheets)
- Each LOB has its own expandable section
- Shows DataFrame with all extracted claims
- Scrollable, full-width tables

#### 📥 Download Button
- Primary blue button
- Downloads `result.xlsx` file

### 5. **Sidebar**
- Company logo (if available)
- Processing Status section:
  - Current status
  - Debug mode indicator
  - File name
  - Result file name
- 🐛 Debug Logs expander (last 50 lines)
- 🔄 Reset Session button
- Directory structure info

## 🎨 Visual Styling

### Color Coding
- ✅ **Success**: Green boxes (#d4edda)
- ❌ **Error**: Red boxes (#f8d7da)
- ℹ️ **Info**: Blue boxes (#d1ecf1)
- ⚠️ **Warning**: Yellow boxes (#fff3cd)

### Typography
- Headers: Large, bold, colored
- Metrics: Large numbers, bold
- Logs: Monospace font in code blocks

## 📱 Responsive Layout
- Wide layout (full screen width)
- Columns adjust automatically
- Tables scroll horizontally if needed
- Charts resize to container width

## 🔄 Interactive Elements

1. **File Uploader**: Drag & drop or click to browse
2. **Debug Mode Toggle**: Checkbox to enable/disable logs
3. **Start Processing Button**: Triggers the workflow
4. **Expandable Sections**: Click to expand/collapse
5. **Download Button**: Downloads Excel file
6. **Reset Button**: Clears session and starts fresh

## 📊 Sample Data Flow

```
Upload PDF → Convert to Text → OpenAI Extraction → Results Display
    ↓              ↓                    ↓                ↓
  backup/      tmp/              results/          Excel Download
sample.pdf   sample_extracted.txt  result.xlsx
```

## 🐛 Debug Mode Features

When **ON**:
- Real-time log capture
- Logs displayed in main area
- Logs stored in sidebar
- All print statements visible
- Processing steps visible

When **OFF**:
- No log display
- Faster execution
- Cleaner interface
- Only final results shown


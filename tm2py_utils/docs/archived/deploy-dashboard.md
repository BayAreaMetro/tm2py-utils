# Deploy Dashboard

Guide to launching and customizing the Streamlit validation dashboard.

## Overview

The validation dashboard is a **Streamlit web application** that visualizes summary data with interactive charts. It displays model-vs-model and model-vs-observed comparisons across multiple datasets.

**Features:**
- Interactive charts (bar, line, scatter, heatmap)
- Multi-dataset comparisons
- Filter by dataset, geography, time period
- Export charts as images
- Fully configurable via YAML

**Technology:** Built with [Streamlit](https://streamlit.io/) and [Plotly](https://plotly.com/python/)

---

## Quick Start

### Prerequisites

Ensure you have the `tm2py-utils` conda environment activated:

```powershell
conda activate tm2py-utils
```

This environment includes Streamlit, Plotly, and all required dependencies.

### Option 1: Launch Dashboard Directly

From the validation directory:

```powershell
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
streamlit run dashboard/dashboard_app.py --server.port 8501
```

**Dashboard opens at:** http://localhost:8501

### Option 2: Generate Summaries + Launch Dashboard

```powershell
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
python run_and_deploy_dashboard.py --config validation_config.yaml --launch-dashboard
```

This:
1. Generates all summaries
2. Copies CSVs to dashboard directory
3. Launches Streamlit

### Option 3: Custom Port

If port 8501 is already in use:

```powershell
streamlit run dashboard/dashboard_app.py --server.port 8503
```

---

## Dashboard Structure

### File Organization

```
tm2py_utils/summary/validation/
├── dashboard/
│   ├── dashboard_app.py           # Main Streamlit app
│   ├── dashboard-households.yaml  # Household charts config
│   ├── dashboard-population.yaml  # Population charts config
│   ├── dashboard-commute.yaml     # Work location charts config
│   ├── dashboard-activity-patterns.yaml  # CDAP charts config
│   ├── dashboard-tours.yaml       # Tour charts config
│   ├── dashboard-trips.yaml       # Trip charts config
│   ├── dashboard-time-of-day.yaml # Time distribution charts config
│   └── dashboard-trip-characteristics.yaml  # Trip distance/duration
├── outputs/
│   └── dashboard/
│       ├── *.csv                  # Combined summary CSVs
│       └── dashboard/             # (Optional) Copied CSVs for deployment
```

### Tab Structure

The dashboard has **8 tabs**, each configured by a YAML file:

| Tab | Config File | Content |
|-----|------------|---------|
| Households | `dashboard-households.yaml` | Auto ownership, household size |
| Population | `dashboard-population.yaml` | Person demographics, CDAP |
| Commute | `dashboard-commute.yaml` | Work location, commute distance |
| Activity Patterns | `dashboard-activity-patterns.yaml` | Daily activity patterns by person type |
| Tours | `dashboard-tours.yaml` | Tour frequency, mode, purpose |
| Trips | `dashboard-trips.yaml` | Trip mode, purpose |
| Time of Day | `dashboard-time-of-day.yaml` | Tour start/end times |
| Trip Characteristics | `dashboard-trip-characteristics.yaml` | Distance, duration distributions |

---

## Dashboard Configuration

### YAML Structure

Each tab is configured with a YAML file:

```yaml
header:
  tab: "Households"
  title: "Household Summary Statistics"
  description: "Household demographics and auto ownership patterns"

layout:
  section_name:
    - type: bar
      title: "Chart Title"
      props:
        dataset: "auto_ownership_regional.csv"
        x: "num_vehicles"
        y: "share"
        groupBy: "dataset"
      description: "Chart description"
```

**Sections:**

| Section | Description |
|---------|-------------|
| `header` | Tab metadata (name, title, description) |
| `layout` | Chart definitions grouped by section |

### Chart Types

#### 1. Bar Chart

```yaml
- type: bar
  title: "Households by Vehicle Ownership"
  props:
    dataset: "auto_ownership_regional.csv"
    x: "num_vehicles"
    y: "share"
    groupBy: "dataset"
```

**Props:**
- `dataset` - CSV filename (in `outputs/dashboard/`)
- `x` - Column for x-axis
- `y` - Column for y-axis (metric)
- `groupBy` - Column for grouping (creates separate bars)
- `facet` - (Optional) Column for faceting (small multiples)
- `columns` - (Optional) Column for sub-grouping within bars

#### 2. Line Chart

```yaml
- type: line
  title: "Tour Distance Distribution"
  props:
    dataset: "tour_distance.csv"
    x: "tour_distance_bin"
    y: "share"
    groupBy: "dataset"
```

**Use for:** Trends, distributions over continuous dimensions

#### 3. Scatter Plot

```yaml
- type: scatter
  title: "Tour Mode vs Purpose"
  props:
    dataset: "tour_mode_by_purpose.csv"
    x: "tour_purpose"
    y: "share"
    groupBy: "tour_mode"
```

**Use for:** Relationships between two continuous variables

#### 4. Heatmap

```yaml
- type: heatmap
  title: "Tour Time of Day Matrix"
  props:
    dataset: "time_of_day_tours.csv"
    x: "start_period"
    y: "end_period"
    z: "tours"
    groupBy: "dataset"
```

**Props:**
- `z` - Values for heatmap color intensity

**Use for:** 2D matrices (start time × end time, origin × destination)

### Faceting (Small Multiples)

Create separate charts for each category:

```yaml
- type: bar
  title: "Auto Ownership by Income"
  props:
    dataset: "auto_ownership_by_income.csv"
    x: "num_vehicles"
    y: "share"
    columns: "dataset"
    facet: "income_category_bin"  # One chart per income category
```

**Result:** 4 side-by-side charts (one per income quartile)

### Grouping

Stack or group bars by a dimension:

```yaml
props:
  x: "tour_purpose"
  y: "tours"
  groupBy: "tour_mode"  # Separate bars for each mode
```

**Result:** Grouped bars showing mode distribution for each purpose

---

## Customizing Charts

### Adding a New Chart

**Step 1:** Identify the summary CSV

Example: `auto_ownership_by_county.csv`

**Step 2:** Choose appropriate YAML file

Example: `dashboard-households.yaml` (for household-related charts)

**Step 3:** Add chart configuration

```yaml
layout:
  auto_ownership_by_county:  # New section
    - type: bar
      title: "Vehicle Ownership by County"
      props:
        dataset: "auto_ownership_by_county.csv"
        x: "county_name"
        y: "share"
        groupBy: "num_vehicles"
      description: "Share of households by vehicle ownership in each county"
```

**Step 4:** Reload dashboard

Dashboard auto-reloads when YAML file changes (Streamlit watches for file changes).

### Creating a New Tab

**Step 1:** Create new YAML file

Example: `dashboard-network.yaml`

```yaml
header:
  tab: "Network"
  title: "Network Performance"
  description: "Highway and transit network statistics"

layout:
  congestion:
    - type: line
      title: "VMT by Time Period"
      props:
        dataset: "vmt_by_period.csv"
        x: "time_period"
        y: "vmt"
        groupBy: "dataset"
```

**Step 2:** Update `dashboard_app.py`

Add to list of dashboard configurations (around line 500):

```python
dashboard_configs = [
    'dashboard-households.yaml',
    'dashboard-population.yaml',
    'dashboard-commute.yaml',
    'dashboard-activity-patterns.yaml',
    'dashboard-tours.yaml',
    'dashboard-trips.yaml',
    'dashboard-time-of-day.yaml',
    'dashboard-trip-characteristics.yaml',
    'dashboard-network.yaml',  # NEW
]
```

**Step 3:** Restart dashboard

### Customizing Colors

Dashboard uses **MTC brand colors** defined in `dashboard_app.py`:

```python
MTC_COLORS = {
    'primary_blue': '#003D7A',
    'teal': '#00A19A',
    'orange': '#ED8B00',
    'purple': '#7A3F93',
    'green': '#8CC63F',
    'red': '#E31937',
}
```

**To change:** Edit color definitions in `dashboard_app.py` and reload.

### Customizing Chart Layout

Edit `PLOTLY_LAYOUT` in `dashboard_app.py`:

```python
PLOTLY_LAYOUT = {
    'font': {'family': 'Inter, Arial, sans-serif', 'size': 13},
    'plot_bgcolor': 'rgba(248, 249, 250, 0.3)',
    'paper_bgcolor': 'white',
    'margin': {'l': 60, 'r': 20, 't': 50, 'b': 70},
}
```

**Customizable:**
- Font family, size, color
- Background colors
- Margins
- Hover behavior

---

## Example Configurations

### Example 1: Simple Bar Chart

**Goal:** Compare vehicle ownership across datasets

```yaml
- type: bar
  title: "Households by Vehicle Ownership"
  props:
    dataset: "auto_ownership_regional.csv"
    x: "num_vehicles"
    y: "share"
    groupBy: "dataset"
  description: "Regional vehicle ownership distribution"
```

**Output:** Grouped bars showing share for each vehicle count, grouped by dataset

### Example 2: Faceted Comparison

**Goal:** Compare income quartiles side-by-side

```yaml
- type: bar
  title: "Auto Ownership by Income Category"
  props:
    dataset: "auto_ownership_by_income.csv"
    x: "num_vehicles"
    y: "share"
    columns: "dataset"
    facet: "income_category_bin"
  description: "Vehicle ownership by income quartile"
```

**Output:** 4 charts (one per income category), each showing dataset comparison

### Example 3: Model vs. ACS Comparison

**Goal:** Compare model to ACS observed data

```yaml
- type: bar
  title: "Auto Ownership by Household Size - Model vs ACS"
  props:
    dataset: "auto_ownership_by_household_size_acs.csv"
    x: "num_persons_agg"
    y: "share"
    columns: "num_vehicles"
    groupBy: "dataset"
    facet: "dataset"
  description: "Vehicle ownership by household size - Model vs ACS 2023"
```

**Output:** Side-by-side charts comparing model runs to ACS data

### Example 4: Heatmap Time Matrix

**Goal:** Visualize tour start/end time patterns

```yaml
- type: heatmap
  title: "Tour Time-of-Day Matrix"
  props:
    dataset: "time_of_day_tours.csv"
    x: "start_period"
    y: "end_period"
    z: "tours"
    groupBy: "dataset"
  description: "Tours by departure and arrival time"
```

**Output:** Heatmap showing tour volume by start time (x) and end time (y)

---

## Running the Dashboard

### Local Development

```powershell
# From validation directory
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
streamlit run dashboard/dashboard_app.py
```

**Features:**
- Auto-reload on file changes
- Debug mode shows errors in browser
- Ctrl+C to stop

### Production Deployment

For hosting on a server:

```bash
streamlit run dashboard/dashboard_app.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --server.headless true
```

**Options:**
- `--server.address 0.0.0.0` - Accept connections from any IP
- `--server.headless true` - Run without opening browser
- `--server.fileWatcherType none` - Disable file watching (saves resources)

### Using Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY tm2py_utils/ ./tm2py_utils/
COPY outputs/dashboard/ ./outputs/dashboard/

EXPOSE 8501

CMD ["streamlit", "run", "tm2py_utils/summary/validation/dashboard/dashboard_app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

Build and run:

```bash
docker build -t tm2-dashboard .
docker run -p 8501:8501 tm2-dashboard
```

---

## Troubleshooting

### Port Already in Use

```
ERROR: Port 8501 is already in use
```

**Solution:** Use a different port

```powershell
streamlit run dashboard/dashboard_app.py --server.port 8503
```

### CSV Not Found

```
FileNotFoundError: auto_ownership_regional.csv
```

**Cause:** Dashboard looks in `outputs/dashboard/` directory

**Solutions:**
1. Run summary generation first
2. Check `output_directory` in `validation_config.yaml`
3. Verify CSV files exist in output directory

### Empty Charts

**Cause:** CSV has no data or wrong column names

**Solutions:**
1. Check CSV has data: `head auto_ownership_regional.csv`
2. Verify column names match YAML `props` exactly
3. Check for case sensitivity (`num_vehicles` ≠ `Num_Vehicles`)

### Module Not Found

```
ModuleNotFoundError: No module named 'streamlit'
```

**Solution:** Activate correct conda environment

```powershell
conda activate tm2py-utils
```

### Encoding Errors

```
UnicodeDecodeError: 'charmap' codec can't decode
```

**Fixed in code** - dashboard_app.py uses `encoding='utf-8'` for YAML files

---

## Advanced Features

### Filtering by Dataset

Dashboard includes sidebar filter:

```python
# In dashboard_app.py
datasets = st.sidebar.multiselect(
    "Select Datasets",
    options=df['dataset'].unique(),
    default=df['dataset'].unique()
)
```

Users can toggle datasets on/off to focus comparisons.

### Exporting Charts

Plotly charts include built-in export:
- Hover over chart
- Click camera icon
- Save as PNG

### Custom Variable Labels

Edit `data_model/variable_labels.yaml`:

```yaml
num_vehicles: "Number of Vehicles"
num_persons: "Household Size"
tour_mode: "Tour Mode"
```

Dashboard uses these labels for axis titles and legends.

### Categorical Ordering

Control order of categorical variables:

```yaml
categorical_order:
  tour_purpose:
    - Work
    - School
    - University
    - Shop
    - Discretionary
  income_category_bin:
    - <30K
    - 30-60K
    - 60-100K
    - 100-150K
    - 150K+
```

Charts display categories in this order (not alphabetical).

---

## Performance Optimization

### Large Datasets

For very large CSVs (>100MB):

**Option 1:** Filter in query

```python
# In dashboard_app.py
df = pd.read_csv(csv_path)
df = df[df['county'] == selected_county]  # Filter before plotting
```

**Option 2:** Use Parquet instead of CSV

```python
# Convert CSV to Parquet
df = pd.read_csv('large_summary.csv')
df.to_parquet('large_summary.parquet')

# Load in dashboard
df = pd.read_parquet('large_summary.parquet')
```

### Caching

Streamlit caches data automatically. For explicit caching:

```python
@st.cache_data
def load_large_dataset(path):
    return pd.read_csv(path)
```

---

## Alternative Visualization Tools

While the system provides a Streamlit dashboard, **summary CSVs can be used with any BI tool:**

### Tableau

1. Load combined CSVs as data sources
2. Use `dataset` column for filtering
3. Create calculated fields for custom metrics

### Power BI

1. Import CSVs via "Get Data" → "Text/CSV"
2. Use `dataset` as slicer
3. Create measures with DAX

### R Shiny

```r
library(shiny)
library(ggplot2)

data <- read.csv("auto_ownership_regional.csv")

ui <- fluidPage(
  selectInput("dataset", "Dataset", unique(data$dataset)),
  plotOutput("plot")
)

server <- function(input, output) {
  output$plot <- renderPlot({
    filtered <- data[data$dataset == input$dataset,]
    ggplot(filtered, aes(x=num_vehicles, y=share)) +
      geom_bar(stat="identity")
  })
}

shinyApp(ui, server)
```

### Observable

Upload CSVs to Observable and create interactive notebooks with D3.js.

---

## Next Steps

- **[Generate Summaries](generate-summaries.md)** - Create summary CSVs for dashboard
- **[Custom Summaries](custom-summaries.md)** - Define new summaries to visualize
- **[External Data Integration](external-data.md)** - Add ACS/CTPP comparisons
- **[Validation System Overview](validation-system.md)** - Return to main guide

---

## Resources

**Streamlit Documentation:**
- https://docs.streamlit.io/
- https://docs.streamlit.io/library/api-reference

**Plotly Documentation:**
- https://plotly.com/python/
- https://plotly.com/python/bar-charts/
- https://plotly.com/python/facet-plots/

**Example Dashboards:**
- Streamlit Gallery: https://streamlit.io/gallery
- Plotly Examples: https://plotly.com/python/

---

## Summary

**To launch dashboard:**
```powershell
conda activate tm2py-utils
cd C:\GitHub\tm2py-utils\tm2py_utils\summary\validation
streamlit run dashboard/dashboard_app.py
```

**To customize:**
1. Edit YAML files in `dashboard/` directory
2. Dashboard auto-reloads on save
3. Add new tabs by creating new YAML files

**Key files:**
- `dashboard_app.py` - Main application
- `dashboard-*.yaml` - Chart configurations
- `outputs/dashboard/*.csv` - Data files

The dashboard is **fully configurable via YAML** - no Python coding required for most customizations.

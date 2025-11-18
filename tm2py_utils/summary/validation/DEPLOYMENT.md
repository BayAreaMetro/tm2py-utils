# Deploying TM2.2 Validation Dashboard to Streamlit Cloud

## Prerequisites
- GitHub account
- Public repository (or Streamlit Teams for private repos)
- Dashboard data files committed to the repository

## Deployment Steps

### 1. Prepare Your Repository

Ensure these files are committed:
```
tm2py_utils/summary/validation/
├── streamlit_app.py              # Entry point for Streamlit Cloud
├── dashboard_app.py              # Main dashboard code
├── requirements.txt              # Python dependencies
├── validation_config.yaml        # Configuration
├── variable_labels.yaml          # Display labels
└── dashboard/                    # Data and config files
    ├── *.csv                     # Summary CSV files
    └── dashboard-*.yaml          # Dashboard configurations
```

### 2. Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click "New app"
3. Connect your GitHub account
4. Select repository: `BayAreaMetro/tm2py-utils`
5. Set branch: `main`
6. Set main file path: `tm2py_utils/summary/validation/streamlit_app.py`
7. Click "Deploy"

### 3. Configuration

The app will automatically:
- Install dependencies from `requirements.txt`
- Load data from the `dashboard/` directory
- Apply MTC branding and styling
- Use dataset ordering from `validation_config.yaml`

### 4. Sharing

Once deployed, you'll get a URL like:
```
https://bayareametro-tm2py-utils-tm2py-utilssummaryvalidatio-xxxxx.streamlit.app
```

Share this URL with stakeholders. The dashboard will:
- Auto-update when you push changes to GitHub
- Handle multiple concurrent users
- Be publicly accessible (or private with Streamlit Teams)

## Updating the Dashboard

To update data or styling:
1. Regenerate summaries: `python -m tm2py_utils.summary.validation.run_all_validation_summaries --config validation_config.yaml`
2. Commit updated CSV files to Git
3. Push to GitHub
4. Streamlit Cloud auto-deploys changes

## Limitations

**Data Size**: Streamlit Cloud has storage limits (~1GB). The current dashboard uses small CSV summary files, which is ideal. Avoid committing large raw model outputs.

**Performance**: Free tier supports moderate traffic. For heavy usage, consider:
- Streamlit Teams (paid)
- Self-hosted deployment
- Data caching optimizations

## Troubleshooting

**App won't start**: Check logs in Streamlit Cloud dashboard
**Import errors**: Verify all dependencies in `requirements.txt`
**Missing data**: Ensure CSV files are committed and paths are relative
**Styling issues**: Clear browser cache, check `.streamlit/config.toml`

## Security Notes

- Dashboard currently reads from committed CSV files
- No authentication by default (add with Streamlit Teams)
- Consider data sensitivity before making repository public
- For internal-only dashboards, use Streamlit Teams private apps

# Streamlit Cloud Deployment Checklist

## ✅ Files Created for Deployment

1. **streamlit_app.py** - Entry point for Streamlit Cloud
2. **requirements.txt** - Dashboard-specific dependencies
3. **.streamlit/config.toml** - Streamlit configuration with MTC theme
4. **DEPLOYMENT.md** - Full deployment instructions

## 📋 Pre-Deployment Checklist

### Required Files (already in repo):
- [x] `tm2py_utils/summary/validation/streamlit_app.py`
- [x] `tm2py_utils/summary/validation/dashboard_app.py`
- [x] `tm2py_utils/summary/validation/requirements.txt`
- [x] `tm2py_utils/summary/validation/validation_config.yaml`
- [x] `tm2py_utils/summary/validation/variable_labels.yaml`
- [x] `tm2py_utils/summary/validation/dashboard/*.csv` (summary data)
- [x] `tm2py_utils/summary/validation/dashboard/*.yaml` (dashboard configs)
- [x] `.streamlit/config.toml`

### Before Deploying:

1. **Commit all dashboard files**:
   ```powershell
   git add tm2py_utils/summary/validation/
   git add .streamlit/
   git commit -m "Add Streamlit Cloud deployment configuration"
   git push origin main
   ```

2. **Verify data files are small enough**:
   - CSV files in dashboard/ folder should be < 10 MB each
   - Total dashboard data < 100 MB recommended
   - Current files are summary CSVs (very small ✅)

3. **Test locally first**:
   ```powershell
   conda activate tm2py-utils
   streamlit run tm2py_utils/summary/validation/streamlit_app.py
   ```

4. **Make repository public** (or use Streamlit Teams for private):
   - Go to GitHub repo settings
   - Under "Danger Zone" → Change visibility

## 🚀 Deploy to Streamlit Cloud

1. Visit: https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Repository: `BayAreaMetro/tm2py-utils`
5. Branch: `main`
6. Main file: `tm2py_utils/summary/validation/streamlit_app.py`
7. Click "Deploy"

## 🔄 Updating the Dashboard

When you have new model runs:

```powershell
# 1. Regenerate validation summaries
conda activate tm2py-utils
python -m tm2py_utils.summary.validation.run_all_validation_summaries --config tm2py_utils\summary\validation\validation_config.yaml --no-dashboard

# 2. Commit and push
cd tm2py_utils\summary\validation
git add dashboard/*.csv
git commit -m "Update validation summaries for [date/version]"
git push origin main

# 3. Streamlit Cloud auto-redeploys in ~1 minute
```

## 🎯 Current Status

- ✅ Dashboard working locally
- ✅ Deployment files created
- ⏳ Ready to commit and push
- ⏳ Ready to deploy to Streamlit Cloud

## 📊 Dashboard Features Deployed

- MTC professional branding with gradient header
- Multi-run comparison (2015 vs 2023)
- Configurable dataset ordering
- Readable variable labels
- Automatic faceting for multi-dimensional data
- Proper percentage formatting
- Categorical variable ordering
- Clean axis labels without overlap

## 🔐 Access Control Options

**Option 1: Public (Free)**
- Anyone with URL can access
- Good for public-facing validation dashboards
- No authentication required

**Option 2: Private with Streamlit Teams**
- Email-based authentication
- Invite specific users
- $250/month for 1 workspace
- Good for internal MTC use

## 📞 Support

- Streamlit Docs: https://docs.streamlit.io/
- Community Forum: https://discuss.streamlit.io/
- Deployment Guide: See DEPLOYMENT.md

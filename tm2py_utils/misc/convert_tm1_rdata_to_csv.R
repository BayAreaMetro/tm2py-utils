# Convert TM1 RData files to CSV for validation
# Run this script from the model output directory

library(data.table)

# Set directories
rdata_dir <- "M:/Application/Model One/RTP2025/IncrementalProgress/2023_TM161_IPA_35/OUTPUT/updated_output"
output_dir <- "M:/Application/Model One/RTP2025/IncrementalProgress/2023_TM161_IPA_35/OUTPUT/ctramp_csv"

# Create output directory if it doesn't exist
if (!dir.exists(output_dir)) {
  dir.create(output_dir, recursive = TRUE)
}

# List of files to convert
rdata_files <- c(
  "households.rdata",
  "persons.rdata", 
  "tours.rdata",
  "trips.rdata",
  "work_locations.rdata",
  "commute_tours.rdata"
)

# Convert each file
for (rdata_file in rdata_files) {
  cat(paste0("\nProcessing: ", rdata_file, "\n"))
  
  rdata_path <- file.path(rdata_dir, rdata_file)
  
  if (!file.exists(rdata_path)) {
    cat(paste0("  [SKIP] File not found: ", rdata_path, "\n"))
    next
  }
  
  # Load the .rdata file
  load(rdata_path)
  
  # The object name in .rdata file (usually matches filename without extension)
  obj_name <- gsub(".rdata$", "", rdata_file, ignore.case = TRUE)
  
  # Get the actual object (may have different name)
  # Try common variations
  possible_names <- c(obj_name, tolower(obj_name), toupper(obj_name))
  
  df <- NULL
  for (name in possible_names) {
    if (exists(name)) {
      df <- get(name)
      cat(paste0("  Found object: ", name, "\n"))
      break
    }
  }
  
  # If still NULL, list all objects loaded
  if (is.null(df)) {
    cat(paste0("  Available objects: ", paste(ls(), collapse=", "), "\n"))
    # Take the first data frame-like object
    obj_list <- ls()
    for (obj in obj_list) {
      temp_obj <- get(obj)
      if (is.data.frame(temp_obj) || is.data.table(temp_obj)) {
        df <- temp_obj
        cat(paste0("  Using object: ", obj, "\n"))
        break
      }
    }
  }
  
  if (is.null(df)) {
    cat(paste0("  [ERROR] No suitable object found in ", rdata_file, "\n"))
    next
  }
  
  # Convert to data frame if needed
  if (is.data.table(df)) {
    df <- as.data.frame(df)
  }
  
  # Create output filename
  csv_filename <- gsub(".rdata$", ".csv", rdata_file, ignore.case = TRUE)
  csv_path <- file.path(output_dir, csv_filename)
  
  # Write to CSV
  cat(paste0("  Writing: ", csv_path, "\n"))
  cat(paste0("  Rows: ", nrow(df), ", Columns: ", ncol(df), "\n"))
  
  fwrite(df, csv_path, row.names = FALSE)
  
  cat(paste0("  [OK] Saved: ", csv_filename, "\n"))
  
  # Clean up
  rm(list = ls()[!(ls() %in% c("rdata_dir", "output_dir", "rdata_files", "rdata_file"))])
}

cat("\n=== CONVERSION COMPLETE ===\n")
cat(paste0("Output directory: ", output_dir, "\n"))

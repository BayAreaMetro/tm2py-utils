"""
CTRAMP Analysis Templates - Pre-built analysis functions for common CTRAMP summaries
"""

import pandas as pd
from typing import Dict, List, Optional
from .ctramp_documentation import MODE_CODES, TIME_PERIODS


class CTRAMPAnalysisTemplates:
    """
    Pre-built analysis templates for common CTRAMP model output summaries
    """
    
    @staticmethod
    def mode_share_analysis(df: pd.DataFrame, mode_field: str = 'trip_mode', 
                          groupby_field: Optional[str] = None) -> pd.DataFrame:
        """
        Calculate mode share by various categories
        
        Args:
            df: DataFrame with trip or tour data
            mode_field: Name of the mode field ('trip_mode' or 'tour_mode')
            groupby_field: Field to group by (e.g., 'tour_purpose', 'income_category')
            
        Returns:
            DataFrame with mode shares
        """
        if groupby_field and groupby_field in df.columns:
            mode_share = df.groupby([groupby_field])[mode_field].value_counts(normalize=True).unstack(fill_value=0)
        else:
            mode_share = df[mode_field].value_counts(normalize=True).to_frame().T
        
        # Convert to percentages and add mode labels
        mode_share_pct = mode_share * 100
        
        # Add mode labels if available
        mode_labels = {}
        for col in mode_share_pct.columns:
            if col in MODE_CODES:
                mode_labels[col] = f"{col}_{MODE_CODES[col]}"
            else:
                mode_labels[col] = str(col)
        
        mode_share_pct = mode_share_pct.rename(columns=mode_labels)
        return mode_share_pct
    
    @staticmethod
    def vmt_calculation(df: pd.DataFrame, distance_field: str = 'TRIP_DISTANCE',
                       mode_field: str = 'trip_mode', groupby_field: Optional[str] = None) -> pd.DataFrame:
        """
        Calculate Vehicle Miles Traveled by various categories
        
        Args:
            df: DataFrame with trip data
            distance_field: Name of the distance field
            mode_field: Name of the mode field
            groupby_field: Field to group by (e.g., 'orig_purpose')
            
        Returns:
            DataFrame with VMT calculations
        """
        # Vehicle modes (drive alone and shared ride)
        vehicle_modes = [1, 2, 3, 4, 5, 6, 7, 8]
        
        # Filter to vehicle trips only
        vehicle_trips = df[df[mode_field].isin(vehicle_modes)].copy()
        
        if groupby_field and groupby_field in vehicle_trips.columns:
            vmt_by_category = vehicle_trips.groupby(groupby_field)[distance_field].sum().reset_index()
            vmt_by_category.columns = [groupby_field, 'VMT']
        else:
            total_vmt = vehicle_trips[distance_field].sum()
            vmt_by_category = pd.DataFrame({'Category': ['Total'], 'VMT': [total_vmt]})
        
        return vmt_by_category
    
    @staticmethod
    def time_of_day_analysis(df: pd.DataFrame, time_field: str = 'stop_period') -> pd.DataFrame:
        """
        Analyze departure/arrival time patterns
        
        Args:
            df: DataFrame with time data
            time_field: Name of the time period field
            
        Returns:
            DataFrame with time-of-day patterns
        """
        tod_pattern = df[time_field].value_counts().sort_index().reset_index()
        tod_pattern.columns = ['time_period', 'count']
        
        # Add time labels
        tod_pattern['time_label'] = tod_pattern['time_period'].map(TIME_PERIODS)
        tod_pattern['percentage'] = (tod_pattern['count'] / tod_pattern['count'].sum()) * 100
        
        return tod_pattern
    
    @staticmethod
    def trip_length_distribution(df: pd.DataFrame, distance_field: str = 'TRIP_DISTANCE',
                               bins: List[float] = None) -> pd.DataFrame:
        """
        Analyze trip length distribution
        
        Args:
            df: DataFrame with trip data
            distance_field: Name of the distance field
            bins: Distance bins for categorization
            
        Returns:
            DataFrame with trip length distribution
        """
        if bins is None:
            bins = [0, 1, 3, 5, 10, 20, 50, float('inf')]
        
        labels = []
        for i in range(len(bins)-1):
            if bins[i+1] == float('inf'):
                labels.append(f"{bins[i]}+ miles")
            else:
                labels.append(f"{bins[i]}-{bins[i+1]} miles")
        
        df_clean = df[df[distance_field].notna() & (df[distance_field] >= 0)].copy()
        df_clean['distance_category'] = pd.cut(df_clean[distance_field], bins=bins, labels=labels, right=False)
        
        length_dist = df_clean['distance_category'].value_counts().reset_index()
        length_dist.columns = ['distance_category', 'count']
        length_dist['percentage'] = (length_dist['count'] / length_dist['count'].sum()) * 100
        length_dist = length_dist.sort_values('distance_category')
        
        return length_dist
    
    @staticmethod
    def tour_generation_rates(df: pd.DataFrame, person_df: pd.DataFrame = None,
                            tour_purpose_field: str = 'tour_purpose') -> pd.DataFrame:
        """
        Calculate tour generation rates by person type
        
        Args:
            df: DataFrame with tour data
            person_df: DataFrame with person data (for person type info)
            tour_purpose_field: Name of the tour purpose field
            
        Returns:
            DataFrame with tour generation rates
        """
        # Count tours by household and person
        tours_by_person = df.groupby(['hh_id', 'person_id']).size().reset_index(name='total_tours')
        
        # If person data provided, merge for person characteristics
        if person_df is not None:
            tours_by_person = tours_by_person.merge(
                person_df[['hh_id', 'person_id', 'person_type']], 
                on=['hh_id', 'person_id'], 
                how='left'
            )
            
            # Calculate average tours by person type
            avg_tours = tours_by_person.groupby('person_type')['total_tours'].agg([
                'mean', 'std', 'count'
            ]).reset_index()
            avg_tours.columns = ['person_type', 'avg_tours_per_person', 'std_dev', 'sample_size']
        else:
            # Overall average
            avg_tours = pd.DataFrame({
                'category': ['All Persons'],
                'avg_tours_per_person': [tours_by_person['total_tours'].mean()],
                'std_dev': [tours_by_person['total_tours'].std()],
                'sample_size': [len(tours_by_person)]
            })
        
        return avg_tours
    
    @staticmethod
    def accessibility_summary(df: pd.DataFrame, mgra_lookup: pd.DataFrame = None,
                            accessibility_fields: List[str] = None) -> pd.DataFrame:
        """
        Summarize accessibility measures by geography
        
        Args:
            df: DataFrame with accessibility data
            mgra_lookup: DataFrame with MGRA to geography mappings
            accessibility_fields: List of accessibility field names
            
        Returns:
            DataFrame with accessibility summaries
        """
        if accessibility_fields is None:
            # Auto-detect accessibility fields
            accessibility_fields = [col for col in df.columns if 'access' in col.lower() and col != 'mgra']
        
        if mgra_lookup is not None and 'mgra' in df.columns:
            # Join with geographic lookup
            df_with_geo = df.merge(mgra_lookup, on='mgra', how='left')
            
            # Summarize by geographic areas (e.g., county)
            geo_fields = [col for col in mgra_lookup.columns if col != 'mgra']
            
            summaries = []
            for geo_field in geo_fields:
                if geo_field in df_with_geo.columns:
                    geo_summary = df_with_geo.groupby(geo_field)[accessibility_fields].agg([
                        'mean', 'median', 'std'
                    ]).reset_index()
                    geo_summary['geography_type'] = geo_field
                    summaries.append(geo_summary)
            
            if summaries:
                return pd.concat(summaries, ignore_index=True)
        
        # Overall summary if no geography available
        overall_summary = df[accessibility_fields].agg(['mean', 'median', 'std']).T.reset_index()
        overall_summary.columns = ['accessibility_measure', 'mean', 'median', 'std']
        overall_summary['geography_type'] = 'Overall'
        
        return overall_summary
    
    @staticmethod
    def transit_boarding_analysis(df: pd.DataFrame, board_field: str = 'trip_board_tap',
                                alight_field: str = 'trip_alight_tap') -> pd.DataFrame:
        """
        Analyze transit boarding and alighting patterns
        
        Args:
            df: DataFrame with transit trip data
            board_field: Name of the boarding TAP field
            alight_field: Name of the alighting TAP field
            
        Returns:
            DataFrame with boarding/alighting summaries
        """
        # Filter to transit trips (modes 11-14)
        transit_modes = [11, 12, 13, 14]
        if 'trip_mode' in df.columns:
            transit_trips = df[df['trip_mode'].isin(transit_modes)].copy()
        else:
            transit_trips = df.copy()
        
        # Boarding analysis
        boardings = transit_trips[board_field].value_counts().reset_index()
        boardings.columns = ['TAP', 'boardings']
        
        # Alighting analysis
        alightings = transit_trips[alight_field].value_counts().reset_index()
        alightings.columns = ['TAP', 'alightings']
        
        # Combine
        tap_activity = boardings.merge(alightings, on='TAP', how='outer', suffixes=('_board', '_alight'))
        tap_activity = tap_activity.fillna(0)
        tap_activity['total_activity'] = tap_activity['boardings'] + tap_activity['alightings']
        tap_activity = tap_activity.sort_values('total_activity', ascending=False)
        
        return tap_activity


# Summary analysis templates dictionary
SUMMARY_TEMPLATES = {
    'mode_share': {
        'description': 'Calculate mode share by various demographics and geography',
        'applicable_files': ['indivTourData', 'indivTripData', 'jointTourData', 'jointTripData'],
        'key_fields': ['tour_mode', 'trip_mode'],
        'groupby_options': ['tour_purpose', 'income_category', 'person_type', 'time_period'],
        'function': CTRAMPAnalysisTemplates.mode_share_analysis
    },
    
    'vmt_calculation': {
        'description': 'Calculate Vehicle Miles Traveled by various categories',
        'applicable_files': ['indivTripData', 'jointTripData'],
        'key_fields': ['TRIP_DISTANCE', 'trip_mode'],
        'vehicle_modes': [1, 2, 3, 4, 5, 6, 7, 8],
        'function': CTRAMPAnalysisTemplates.vmt_calculation
    },
    
    'time_of_day': {
        'description': 'Analyze departure/arrival time patterns',
        'applicable_files': ['indivTourData', 'indivTripData'],
        'key_fields': ['start_period', 'end_period', 'stop_period'],
        'function': CTRAMPAnalysisTemplates.time_of_day_analysis
    },
    
    'trip_length_distribution': {
        'description': 'Analyze distribution of trip distances',
        'applicable_files': ['indivTripData', 'jointTripData'],
        'key_fields': ['TRIP_DISTANCE'],
        'function': CTRAMPAnalysisTemplates.trip_length_distribution
    },
    
    'tour_generation': {
        'description': 'Calculate tour generation rates by person characteristics',
        'applicable_files': ['indivTourData'],
        'key_fields': ['tour_purpose', 'person_type'],
        'function': CTRAMPAnalysisTemplates.tour_generation_rates
    },
    
    'accessibility_summary': {
        'description': 'Summarize accessibility measures by geography and demographics',
        'applicable_files': ['accessibilities.csv'],
        'key_fields': ['mgra'],
        'function': CTRAMPAnalysisTemplates.accessibility_summary
    },
    
    'transit_boarding': {
        'description': 'Analyze transit boarding and alighting patterns',
        'applicable_files': ['indivTripData', 'indivTripDataResim'],
        'key_fields': ['trip_board_tap', 'trip_alight_tap'],
        'function': CTRAMPAnalysisTemplates.transit_boarding_analysis
    }
}


def get_summary_template(analysis_type: str) -> Dict:
    """
    Get a pre-built analysis template
    
    Args:
        analysis_type: Type of analysis template to retrieve
        
    Returns:
        Dictionary with template information
    """
    return SUMMARY_TEMPLATES.get(analysis_type, {})


def list_applicable_summaries(filename: str) -> List[str]:
    """
    List all applicable summary analyses for a given file
    
    Args:
        filename: Name of the file to check
        
    Returns:
        List of applicable analysis types
    """
    applicable = []
    for analysis_type, template in SUMMARY_TEMPLATES.items():
        if any(file_pattern in filename for file_pattern in template['applicable_files']):
            applicable.append(analysis_type)
    return applicable


def show_analysis_recommendations(filename: str, file_columns: List[str] = None):
    """
    Show specific analysis recommendations for a file
    
    Args:
        filename: Name of the file
        file_columns: List of column names in the file
    """
    from .ctramp_documentation import get_analysis_guidance
    
    print(f"\n🎯 ANALYSIS RECOMMENDATIONS FOR: {filename}")
    print("="*60)
    
    # Get guidance
    guidance = get_analysis_guidance(filename)
    if not guidance:
        print("❓ No specific guidance available for this file type")
        return
    
    print(f"📝 Purpose: {guidance.get('purpose', 'No description')}")
    
    print(f"\n🔍 Common Summaries:")
    for summary in guidance.get('common_summaries', []):
        print(f"   • {summary}")
    
    print(f"\n📊 Key Fields for Analysis:")
    key_fields = guidance.get('key_fields_for_analysis', [])
    for field in key_fields:
        available = "✅" if file_columns and field in file_columns else "❓"
        print(f"   {available} {field}")
    
    print(f"\n🛠️ Applicable Analysis Templates:")
    templates = list_applicable_summaries(filename)
    for template in templates:
        template_info = SUMMARY_TEMPLATES[template]
        print(f"   • {template}: {template_info['description']}")
    
    # Show any special analysis notes
    for note_type in ['geographic_aggregation', 'model_validation', 'join_keys', 'vmt_calculation']:
        if note_type in guidance:
            print(f"\n💡 {note_type.replace('_', ' ').title()}: {guidance[note_type]}")
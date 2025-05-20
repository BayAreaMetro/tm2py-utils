<#
.SYNOPSIS
  Create, start, and stop a PerfMon data-collector set to CSV.

.DESCRIPTION
  Uses logman.exe under the hood to collect a fixed set of CPU, system,
  memory, disk and network counters at a configurable sample interval,
  writing out to CSV files in the specified folder.

.PARAMETER Action
  'Start' to create & start the collector; 'Stop' to stop & delete it.

.PARAMETER OutputFolder
  Folder where CSV files will be dropped (only used with -Action Start).

.PARAMETER SampleIntervalSeconds
  How often (in seconds) to sample each counter.

.PARAMETER NetworkInterfaceName
  Exact name of the NIC instance to monitor.  Defaults to wildcard (*) if omitted.

.EXAMPLE
  # Start logging at 5-second intervals:
  .\PerfMon-TM2.ps1 -Action Start `
    -OutputFolder "C:\PerfLogs\TM2Run1" `
    -SampleIntervalSeconds 5 `
    -NetworkInterfaceName "vmxnet3 Ethernet Adapter"

  # Stop & clean up after the run:
  .\PerfMon-TM2.ps1 -Action Stop
#>

param(
    [Parameter(Mandatory,$true)]
    [ValidateSet("Start","Stop")]
    [string] $Action,

    [string] $OutputFolder = "E:\TM2.2.1.3_clean_setup",

    [int] $SampleIntervalSeconds = 15,

    [string] $NetworkInterfaceName = "*"
)

# Name of the data collector set  
$SetName = "TM2PerfMonitor"

# Define the exact counters to collect
$counters = @(
    # CPU (Total)
    "\Processor(_Total)\% Processor Time",
    "\Processor(_Total)\% Privileged Time",
    "\Processor(_Total)\% DPC Time",
    "\Processor(_Total)\% Interrupt Time",

    # System
    "\System\Processor Queue Length",
    "\System\Context Switches/sec",

    # Memory
    "\Memory\% Committed Bytes In Use",
    "\Memory\Available MBytes",
    "\Memory\Pages/sec",

    # Disk (Total)
    "\PhysicalDisk(_Total)\% Disk Time",
    "\PhysicalDisk(_Total)\Avg. Disk sec/Read",
    "\PhysicalDisk(_Total)\Avg. Disk sec/Write",
    "\PhysicalDisk(_Total)\Current Disk Queue Length",

    # Network (specified interface or all via wildcard)
    "\Network Interface($NetworkInterfaceName)\Bytes Total/sec"
)

function Remove-ExistingCollector {
    # suppress errors if not present
    logman.exe delete $SetName -ets 2>$null
}

if ($Action -eq "Start") {
    # 1) Ensure output folder exists
    if (!(Test-Path $OutputFolder)) {
        New-Item -ItemType Directory -Path $OutputFolder -Force | Out-Null
    }

    # 2) Remove any prior definition
    Remove-ExistingCollector

    # 3) Create the counter set (CSV format)
    logman.exe create counter $SetName `
        -c $counters `
        -si $SampleIntervalSeconds `
        -f CSV `
        -o "$OutputFolder\$SetName" | Out-Null

    # 4) Start it immediately
    logman.exe start $SetName

    Write-Host "[$(Get-Date -Format u)] Started collector '$SetName'."
    Write-Host "Logging every $SampleIntervalSeconds sec to: $OutputFolder\$SetName*.csv"
}
elseif ($Action -eq "Stop") {
    # 1) Stop logging
    logman.exe stop $SetName

    # 2) Delete the collector definition
    Remove-ExistingCollector

    Write-Host "[$(Get-Date -Format u)] Stopped and removed collector '$SetName'."
}
else {
    Write-Error "Unknown action '$Action'. Use -Action Start or Stop."
}

# Run on the custodian's own offline Windows device, outside executor-accessible
# accounts, Git checkouts and synced folders. The output is public; the file is not.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$OutputFile
)
$ErrorActionPreference = 'Stop'
$dest = [IO.Path]::GetFullPath($OutputFile)
$parent = [IO.Path]::GetDirectoryName($dest)
if (-not [IO.Directory]::Exists($parent)) { throw 'Choose an existing private directory.' }
$seedBytes = [byte[]]::new(32)
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$hash = [Security.Cryptography.SHA256]::Create()
try {
    $rng.GetBytes($seedBytes)
    $expected = [BitConverter]::ToString($hash.ComputeHash($seedBytes)).Replace('-', '').ToLowerInvariant()
    # CreateNew never overwrites a previous seed. Do not retry after a failed
    # write or verification; preserve the file for custody review.
    $stream = [IO.File]::Open($dest, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($seedBytes, 0, $seedBytes.Length); $stream.Flush($true) }
    finally { $stream.Dispose() }
    $f = [IO.File]::OpenRead($dest)
    try {
        if ($f.Length -ne 32) { throw 'File length mismatch; withhold this commitment.' }
        $actual = [BitConverter]::ToString($hash.ComputeHash($f)).Replace('-', '').ToLowerInvariant()
    } finally { $f.Dispose() }
    if ($actual -cne $expected) { throw 'Readback mismatch; withhold this commitment.' }
    Write-Output ('H3=' + $actual)
} finally {
    [Array]::Clear($seedBytes, 0, $seedBytes.Length)
    $rng.Dispose()
    $hash.Dispose()
}

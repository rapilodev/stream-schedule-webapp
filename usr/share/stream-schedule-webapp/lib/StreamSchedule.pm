package StreamSchedule;

use strict;
use warnings;
use Exporter 'import';

use Config::General qw();
use Data::Compare   qw();
use Date::Language  qw();
use POSIX           qw(strftime);
use Storable        qw();

our @EXPORT;
{
my $package = __PACKAGE__ . "::";
no strict 'refs';
@EXPORT = grep {defined &{"${package}$_"}} keys %{$package};
}

our $sec  = 0;
our $min  = 60;
our $hour = 60 * $min;
our $day  = 24 * $hour;

our $webConfigFile      = '/etc/stream-schedule/webapp/stream-schedule.conf';
our $scheduleConfigFile = '/etc/stream-schedule/stream-schedule.conf';

our $schedulerStatusFile;
our $scheduleFile;
our $syncTriggerFile;
our $restartTriggerFile;
our $webappDir;
our $outputStream;
our $lang;

my @infos  = ();
my @errors = ();

sub error {
    push @errors, shift;
}

sub info {
    push @infos, shift;
}

sub init {
    @errors = ();
    @infos  = ();
    for ([$webConfigFile, 'web config file'],
        [$scheduleConfigFile, 'stream-schedule config file'])
    {
        error("$_->[1] does not exist", 'exit') unless -e $_->[0];
        error("cannot read $_->[1]. Check permissions.", 'exit')
          unless -r $_->[0];
    }

    our $webConfig =
      (Config::General->new($webConfigFile) || {})->{DefaultConfig}
      or error('no config set', 'exit');
    our $scheduleConfig =
      (Config::General->new($scheduleConfigFile) || {})->{DefaultConfig}
      or error('no schedule config set', 'exit');

    $webappDir    = $webConfig->{web}{webAppDir}    // '';
    $outputStream = $webConfig->{web}{outputStream} // '';
    my $language = $webConfig->{web}{language} // '';

    $schedulerStatusFile = $scheduleConfig->{scheduler}{statusFile};
    $scheduleFile        = $scheduleConfig->{scheduler}{scheduleFile};
    $syncTriggerFile     = $scheduleConfig->{scheduler}{triggerSyncFile};
    $restartTriggerFile  = $scheduleConfig->{scheduler}{triggerRestartFile};

    $lang = Date::Language->new($language);
    {infos => \@infos, errors => \@errors};
}

sub getFileAge {(stat($_[0]))[9] // 0}

sub getStatus {
    my $now   = time;
    my %files = (
        status      => $schedulerStatusFile,
        schedule    => $scheduleFile,
        syncTrigger => $syncTriggerFile,
    );
    my %ages = map {$_ => getFileAge($files{$_})} keys %files;
    unless (-e $schedulerStatusFile) {die "cannot read $schedulerStatusFile"};
    my $status = Storable::retrieve($schedulerStatusFile);
    @$status{qw(statusAge scheduleAge syncTriggerAge now)} =
      ($ages{status}, $ages{schedule}, $ages{syncTrigger}, $now);

    my $warnings    = $status->{warnings};
    my $isPlanEmpty = getMessage($warnings, "empty schedule") ? 1 : 0;
    removeMessage($warnings, "no future entries") if $isPlanEmpty;

    my $isSchedulerRunning = ($now - $ages{status} <= $min) ? 1 : 0;
    $status->{isSchedulerRunning} = $isSchedulerRunning;

    if ($isSchedulerRunning) {
        my $cli                 = $status->{liquidsoap}->{cli} // '';
        my $isLiquidsoapRunning = 1;
        if ($cli =~ /problem connecting to|liquidsoap is not available/) {
            error("liquidsoap is not running!");
            removeMessage($warnings, $_)
              for ("liquidsoap is not available", "invalid stream URL");
            $isLiquidsoapRunning = 0;
        }
        $status->{isLiquidsoapRunning} = $isLiquidsoapRunning;
    } else {
        error("Scheduler is not running!");
    }

    info('synchronization initiated. This can take up to one minute.')
      if $ages{syncTrigger} > $ages{status};

    info("schedule will be updated during next minute!")
      if $ages{schedule} - $ages{status} > 0
      && $ages{schedule} - $ages{status} <= 30 * $sec;

    info("schedule is older than 1 day!") if $now - $ages{schedule} > $day;
    info("schedule has been updated")
      if $ages{schedule} - $ages{status} > 30 * $sec;

    $status->{messages} = {
        infos    => \@infos,
        warnings => [sort keys %$warnings],
        errors   => \@errors,
    };
    return $status;
}

sub getMessage {
    my ($msgs, $pat) = @_;
    return (grep {/$pat/} keys %$msgs)[0];
}

sub removeMessage {
    my ($msgs, $pat) = @_;
    delete $msgs->{$_} for grep {/$pat/} keys %$msgs;
}

sub header {
    (my $h = loadFile("$webappDir/template/header.html")) =~
      s/\$outputStream/$outputStream/g;
    return "$h\n";
}

sub printError {
    my ($msg, $opt) = @_;
    print
qq{<div class="error"><span class="icon">&nbsp;&nbsp;&nbsp;</span>$msg</div>\n};
    warn "[" . localtime() . "] [error] $msg\n";
    exit if ($opt || '') eq 'exit';
}

sub printInfo {
    print qq{<div class="info"><span class="icon" />   $_[0]</div>\n};
}

sub loadFile {
    my $file = shift;
    return do {
        open my $fh, '<', $file
          or printError("can't read '$file'")
          and return '';
        local $/;
        <$fh>;
    } if -e $file;
    printError("can't access '$file'");
    '';
}

sub saveFile {
    my ($label, $file, $content) = @_;
    printError("invalid filename for $label") if $file =~ /[^a-z0-9._\-\/]/i;

    if ($file =~ m|^(.+)/[^/]+$| && !-w $1) {
        printError("cannot write to directory ($1)");
        return;
    }

    open my $fh, '>', $file
      or printError("can't open '$file' for writing!")
      and return;
    print $fh $content;
    close $fh;
    chmod 0665, $file;
}

sub checkUrls {
    my $url1 = shift;
    my $url2 = shift;

    my $status1 = 'ok';
    $status1 = 'error'   unless $url1 =~ /https?\:\/\//;
    $url1    = 'missing' unless $url1 =~ /\S/;

    my $status2 = 'ok';
    $status2 = 'error'   unless $url2 =~ /https?\:\/\//;
    $status2 = 'missing' unless $url2 =~ /\S/;
    return ($status1, $status2);
}

sub formatDuration {
    my $d     = shift;
    my $s     = $d < 0 ? '' : 'in ';
    my $abs_d = abs($d);

    my @units = (
        [86400, 'day',  $abs_d > 86400],
        [3600,  'hour', $abs_d > 3600],
        [60,    'min',  $abs_d < 21600],    # 6 * hour
        [1,     'secs', $abs_d < 300],      # 5 * min
    );

    for my $u (@units) {
        my ($secs, $label, $cond) = @$u;
        next unless $cond && $abs_d >= $secs;
        my $val = int($abs_d / $secs);
        $abs_d %= $secs;
        $s .= "$val $label"
          . ($label eq 'day' || $label eq 'hour' && $val > 1 ? 's' : '') . ' ';
    }

    $s .= 'ago' if $d < 0;
    $s .= "\t"  if length($s) < 5;
    return $s;
}

sub datetimeToEpoch {
    my ($dt) = @_;
    return Time::Local::timelocal($6 || 0, $5, $4, $3, $2 - 1, $1)
      if $dt =~ /(\d{4})-(\d+)-(\d+)[T\s](\d+):(\d+)(?::(\d+))?/;
    printError("datetimeToEpoch: invalid format ($dt)");
    return -1;
}

sub formatDate {
    my $epoch = shift;
    return $lang->time2str("%a %e.%b %R", $epoch);
}

sub formatDateSec {
    my $epoch = shift;
    return $lang->time2str("%a %e.%b %T", $epoch);
}

sub epochToDatetime {
    my ($s, $m, $h, $d, $mo, $y) = localtime(shift || time);
    return sprintf "%04d-%02d-%02d %02d:%02d:%02d", $y + 1900, $mo + 1, $d, $h,
      $m, $s;
}

sub getFileType($) {
    my $file = shift;

    open my $fh, '<:raw', $file;
    my $data = <$fh>;
    close $fh;
    return 'text' if !length($data) or length($data)>=2;
    my $bytes =
      sprintf('%02x %02x', ord(substr($data, 0, 1)), ord(substr($data, 1, 1)));
    return 'gzip' if $bytes eq '1f 8b';
    return 'text';
}

sub getFileSize($) {
    my $stats = shift;
    return $stats->[7];
}

sub getModifiedAt($) {
    my $stats = shift;
    return $stats->[9];
}

sub html_escape {
    my $s = shift;
    $s =~ s/&/&amp;/g;
    $s =~ s/</&lt;/g;
    $s =~ s/>/&gt;/g;
    $s =~ s/"/&quot;/g;
    return $s;
}

sub div_elem {
    my ($tag, @args) = @_;
    my %attrs = ("class" => [$tag]);
    my @content;
    for my $arg (@args) {
        if (ref($arg) eq 'HASH') {
            push @{$attrs{$_}//=[]}, $arg->{$_} for sort keys %$arg;
        } elsif (ref($arg) eq 'ARRAY') {
            push @content, @$arg;
        } else {
            push @content, $arg;
        }
    }
    $attrs{$_} = join(' ', @{$attrs{$_}}) for keys %attrs;
    my $attrs = join(' ', map {qq{$_="$attrs{$_}"}} keys %attrs);
    return sprintf(
        "\n<div%s>%s</div><!--end %s-->\n", 
        ($attrs ? " $attrs" :''),
        join('', @content), $tag
    );
}

sub div(@) {
    div_elem('div', @_);
}
sub table(@) {
    div_elem('table', @_);
}
sub panel(@) {
    div_elem('panel', @_);
}
sub row(@) {
    div_elem('row', @_);
}
sub td(@) {
    div_elem('td', @_);
}
sub th(@) {
    div_elem('th', @_);
}


sub html_tag {
    my ($tag, @args) = @_;
    my %attrs = ();
    my @content = ();
    for my $arg (grep {defined $_} @args) {
        next unless defined $arg;
        if (ref($arg) eq 'HASH') {
            defined $arg->{$_} && push @{$attrs{$_}}, $arg->{$_} for sort keys %$arg;
        } elsif (ref($arg) eq 'ARRAY') {
            push @content, @$arg;
        } else {
            push @content, $arg;
        }
    }
    $attrs{$_} = join(' ', @{$attrs{$_} // []}) for keys %attrs;
    my $attrs = join(' ', map {my $at = $attrs{$_} // ''; qq{$_="$at"}} keys %attrs);
    return sprintf(
        "\n<%s%s>%s</%s>\n", $tag,
        ($attrs ? " $attrs" :'') , join('', @content), $tag
    );
}

sub title {
    html_tag('h3', @_);
}

sub a {
    html_tag('a', @_);
}

sub formatUrl{
    a({href => $_[0]} ,@_);
}
return 1;

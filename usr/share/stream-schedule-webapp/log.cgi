#!/usr/bin/perl
use strict;
use warnings;

use CGI::Simple();
use Time::HiRes qw(time);
use File::Basename();
use PerlIO::gzip();
use Time::Local();
use Config::General();

our $webConfigFile = '/etc/stream-schedule/webapp/stream-schedule.conf';
our $webappDir     = '.';
our $outputStream  = '';

my $MB    = 1024 * 1024;
my $debug = 0;

my $settings = {
    liquidsoap => {
        name      => 'liquidsoap',
        files     => '/var/log/stream-schedule/liquidsoap.log',
        blacklist => [
            'client disconnected',
            'New client: ',
            'Client disconnected',
            'disconnected without',
            'Re-opening output file',
            'try again in '
        ],
    },
    liquidsoap2 => {
        name      => 'liquidsoap2',
        files     => '/var/log/stream-schedule/radio.log',
        blacklist => [
            'client disconnected',
            'New client: ',
            'Client disconnected',
            'disconnected without',
            'Re-opening output file',
            'try again in '
        ],
    },
    scheduler => {
        name      => 'scheduler',
        files     => '/var/log/stream-schedule/scheduler.log',
        blacklist => [
            "skip", "buildDataFile()", "plot()", "checkSleep()",
            "printStatus()"
        ]
    },
    icecast => {
        name      => 'icecast2',
        files     => '/var/log/icecast2/error.log',
        blacklist => [
            "checking for file /radio1",
            "checking for file /radio2",
            '/web/radio1" No such file or directory',
            '/web/radio2" No such file or directory',
            'fserve/fserve_client_create'
        ]
    },
};

binmode STDOUT, ":encoding(UTF-8)";

sub epochToDatetime {
    my ($s, $m, $h, $d, $mo, $y) = localtime(shift || time);
    return sprintf "%04d-%02d-%02d %02d:%02d:%02d", $y + 1900, $mo + 1, $d, $h,
      $m, $s;
}

sub loadFile {
    my $f = shift;
    return '' unless -e $f;
    open my $fh, '<', $f or printError("can't read file '$f'!") && return '';
    local $/;
    my $c = <$fh>;
    close $fh;
    return $c;
}

sub printError {
    print qq{<div class="error"><span class="icon">⚠️</span>$_[0]</div>};
    exit if $_[1] && $_[1] eq 'exit';
}

sub getFileType($) {
    my $file = shift;

    open my $fh, '<:raw', $file;
    my $data = <$fh>;
    close $fh;

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

sub parseFile {
    my $linesByDate = shift;
    my $file        = shift;
    my $targetDate  = shift;
    my $blackList   = shift;
    my $name        = shift;

    my ($year, $month, $day) = split /\-/, $targetDate;
    my $targetEpoch =
      Time::Local::timelocal(0, 0, 0, $day, $month - 1, $year - 1900)
      ;    #+ 24 * 60 *60;

    my @stats = stat $file;

    my $modifiedAt = getModifiedAt(\@stats);
    if ($modifiedAt < $targetEpoch) {
        print
"file $file is too old, modifiedAt=$modifiedAt, targetEpoch=$targetEpoch \n";
        return undef;
    }

    my $fileType = getFileType($file);
    my $size     = getFileSize(\@stats);
    if (($fileType eq 'text') && ($size > 5 * $MB)) {
        print "$file is to big! ignore...\n";
        return undef;
    } elsif (($fileType eq 'gzip') && ($size > 1 * $MB)) {
        print "$file is to big! ignore...\n";
        return undef;
    }

    my $cmd = undef;
    if ($fileType eq 'gzip') {
        open $cmd, "<:gzip", $file or die $!;
    } elsif ($fileType =~ /text/) {
        open $cmd, '<', $file;
    } else {
        print "file $file ($fileType): could not open to read\n";
        return undef;
    }

    my $dateMatch =
qr/([\[]?(\d\d\d\d)[\s\-\/]+(\d\d)[\s\-\/]+(\d\d)[\sT]+(\d\d)\:(\d\d)\:(\d\d)[\]]?\s+)/;
    my $duplicate    = 1;
    my $line         = '';
    my $previousLine = '';
    my $datetime     = '';

    my $blackMatch = '(' . join("|", @$blackList) . ')';
    $blackMatch = qr/$blackMatch/;

    my $matchCounter = 0;
    my $lineCounter  = 0;
    while (<$cmd>) {
        $line = $_;
        $lineCounter++;

        if ($line =~ /$dateMatch/) {
            my $match = $1;
            my $year  = $2;
            my $month = $3;
            my $day   = $4;
            my $hour  = $5;
            my $min   = $6;
            my $sec   = $7;
            my $date  = $year . "-" . $month . "-" . $day;

            if ($date lt $targetDate) {
                next;
            } elsif ($date gt $targetDate) {
                printf("file %s: found %d of %d lines\n",
                    $file, $matchCounter, $lineCounter);
                return 1;
            }
            $datetime = $date . " " . $hour . ":" . $min . ":" . $sec;
            $line     = substr($line, length($match));
        }

        #add blacklist parameters
        next if $line =~ /$blackMatch/;

        $linesByDate->{$datetime} = [] unless defined $linesByDate->{$datetime};
        my $lines = $linesByDate->{$datetime};

        if ($line eq $previousLine) {
            $duplicate++;
            next;
        } elsif (($duplicate > 1) && (scalar(@$lines) > 1)) {
            $lines->[-1] =~ s/\n$//g;
            $lines->[-1] .= " [$duplicate times]\n";
            $duplicate = 1;
        }

        $previousLine = $line;
        $line         = $datetime . "\t" . $name . "\t" . $line;
        $matchCounter++;
        push @$lines, $line;

    }
    close $cmd;
    printf("file %s: found %d of %d lines\n",
        $file, $matchCounter, $lineCounter);
    return 1;
}

#rver:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] New client: localhost.

sub parseFiles {
    my ($year, $month, $day) = @_;
    my $targetDate = "$year-$month-$day";
    my ($files, $filesParsed, %linesByDate);

    print q{<div class="panel" style="text-align:left;">};
    my $start = time();

    for my $proc (sort keys %$settings) {
        my $s = $settings->{$proc};
        my ($name, $blackList, $path) = @$s{qw(name blacklist files)};
        my $dir = File::Basename::dirname($path);

        unless (-d $dir) {
            warn "skip $dir\n";
            next;
        }

        my $pattern = qr/\Q$path\E(?:\.\d+)?(?:\.gz)?$/;
        opendir my $dh, $dir or next;

        for my $file (readdir $dh) {
            $file = "$dir/$file";
            next unless $file =~ $pattern;
            $files++;
            $filesParsed++
              if parseFile(\%linesByDate, $file, $targetDate, $blackList,
                $name);
        }
        closedir $dh;
    }
    printf("<hr>parsed %d of %d files\n", $filesParsed, $files);
    print "</div>";

    print q{<div class="panel" style="text-align:left;">};
    print join "", map {join "", @{$linesByDate{$_}}} sort keys %linesByDate;
    print sprintf("<hr>took %.2f seconds\n", time() - $start);
    print "</div>";
}

my $cgi    = new CGI::Simple();
my $params = $cgi->Vars;

print $cgi->header('text/html;charset=utf-8');
printError('config file does not exist', 'exit') unless -e $webConfigFile;
printError('cannot read config file',    'exit') unless -r $webConfigFile;

my $config = Config::General->new($webConfigFile);
$config = $config->{DefaultConfig};
printError('no config set', 'exit') unless defined $config;
$webappDir    = $config->{web}->{webAppDir};
$outputStream = $config->{web}->{outputStream};

my $header = loadFile($webappDir . "/template/header.html");
$header =~ s/\$outputStream/$outputStream/g;
print $header . q{
    <script type="text/javascript" src="js/log.js"></script>
    <form id="form" action="log.cgi" method="get" style="position:absolute;left:1rem;top:0.5rem">
        Date <input name="date" type="date" class="datepicker" size="30" style="padding:1rem"/>
    </form>
    <div style="padding:1rem; white-space: pre-wrap;">};

$params->{date} = epochToDatetime() if $params->{date} eq 'today';
exit                                if $params->{date} eq '';
if ($params->{date} =~ /(\d\d\d\d)\-(\d\d)\-(\d\d)/) {
    parseFiles($1, $2, $3);
}

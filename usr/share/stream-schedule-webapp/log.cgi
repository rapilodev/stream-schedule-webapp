#/usr/bin/perl
use strict;
use warnings;

use CGI::Simple();
use Data::Dumper;
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
        blacklist => [ "skip", "buildDataFile()", "plot()", "checkSleep()", "printStatus()" ]
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

sub printHeader {

    #print "Content-type:text/plain; charset=utf8\n\n";
    my $header = loadFile( $webappDir . "/template/header.html" );
    $header =~ s/\$outputStream/$outputStream/g;

    $header .= q{
        <link type="text/css" href="css/jquery-ui.min.css" rel="stylesheet" />  
    <script type="text/javascript" src="js/jquery-ui.min.js"></script>
    <script type="text/javascript" src="js/log.js"></script>

    <div class="panel">
    <form id="form" action="log.cgi" method="get">
        <p>Date: <input name="date" type="text" class="datepicker" size="30"/></p>
    </form> 
    <pre>};
    print $header;
}

sub epochToDatetime {
    my $time = shift;

    $time = time() unless ( ( defined $time ) && ( $time ne '' ) );
    ( my $sec, my $min, my $hour, my $day, my $month, my $year ) = localtime($time);
    my $datetime =
      sprintf( "%4d-%02d-%02d %02d:%02d:%02d", $year + 1900, $month + 1, $day, $hour, $min, $sec );
    return $datetime;
}

sub loadFile {
    my $filename = $_[0];

    unless ( -e $filename ) {
        printError("cant access file '$filename'!");
        return '';
    }
    open my $fh, "<", $filename || printError("cant read file '$filename'!");
    local $/ = undef;
    my $content = <$fh>;
    close $fh;
    return $content;
}

sub printError {
    my $message = shift;
    my $option  = shift;
    print qq{<div class="error"><span class="icon" >&nbsp; &nbsp; &nbsp;</span>$message</div>};
    exit if $option eq 'exit';
}

sub getFileType($) {
    my $file = shift;

    open my $fh, '<:raw', $file;
    my $data = <$fh>;
    close $fh;

    my $bytes = sprintf( '%02x %02x', ord( substr( $data, 0, 1 ) ), ord( substr( $data, 1, 1 ) ) );
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

#1524953936
#1527458400

sub parseFile {
    my $linesByDate = shift;
    my $file        = shift;
    my $targetDate  = shift;
    my $blackList   = shift;
    my $name        = shift;

    my ( $year, $month, $day ) = split /\-/, $targetDate;
    my $targetEpoch =
      Time::Local::timelocal( 0, 0, 0, $day, $month - 1, $year - 1900 );    #+ 24 * 60 *60;

    my @stats = stat $file;

    my $modifiedAt = getModifiedAt( \@stats );
    if ( $modifiedAt < $targetEpoch ) {
        print "file $file is too old, modifiedAt=$modifiedAt, targetEpoch=$targetEpoch \n";
        return undef;
    }

    my $fileType = getFileType($file);
    my $size     = getFileSize( \@stats );
    if ( ( $fileType eq 'text' ) && ( $size > 5 * $MB ) ) {
        print "$file is to big! ignore...\n";
        return undef;
    } elsif ( ( $fileType eq 'gzip' ) && ( $size > 1 * $MB ) ) {
        print "$file is to big! ignore...\n";
        return undef;
    }

    my $cmd = undef;
    if ( $fileType eq 'gzip' ) {
        open $cmd, "<:gzip", $file or die $!;
    } elsif ( $fileType =~ /text/ ) {
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

    my $blackMatch = '(' . join( "|", @$blackList ) . ')';
    $blackMatch = qr/$blackMatch/;

    my $matchCounter = 0;
    my $lineCounter  = 0;
    while (<$cmd>) {
        $line = $_;
        $lineCounter++;

        if ( $line =~ /$dateMatch/ ) {
            my $match = $1;
            my $year  = $2;
            my $month = $3;
            my $day   = $4;
            my $hour  = $5;
            my $min   = $6;
            my $sec   = $7;
            my $date  = $year . "-" . $month . "-" . $day;
            if ( $date lt $targetDate ) {
                next;
            } elsif ( $date gt $targetDate ) {
                printf( "file %s: found %d of %d lines\n", $file, $matchCounter, $lineCounter );
                return 1;
            }
            $datetime = $date . " " . $hour . ":" . $min . ":" . $sec;
            $line = substr( $line, length($match) );
        }

        #add blacklist parameters
        next if $line =~ /$blackMatch/;

        $linesByDate->{$datetime} = [] unless defined $linesByDate->{$datetime};
        my $lines = $linesByDate->{$datetime};

        if ( $line eq $previousLine ) {
            $duplicate++;
            next;
        } elsif ( ( $duplicate > 1 ) && ( scalar(@$lines) > 1 ) ) {
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
    printf( "file %s: found %d of %d lines\n", $file, $matchCounter, $lineCounter );
    return 1;
}

#rver:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] New client: localhost.

sub parseFiles {
    my $year  = shift;
    my $month = shift;
    my $day   = shift;

    my $targetDate  = $year . '-' . $month . '-' . $day;
    my $files       = 0;
    my $filesParsed = 0;
    my $linesByDate = {};

    for my $process ( keys %$settings ) {
        my $name      = $settings->{$process}->{name};
        my $blackList = $settings->{$process}->{blacklist};

        my $file = $settings->{$process}->{files};
        my $dir  = File::Basename::dirname($file);
        unless ( -d $dir ) {
            print STDERR "skip $dir\n";
            next;
        }

        # build filter pattern
        my $filePattern = quotemeta($file) . '(\.\d+)?(\.gz)?$';
        $filePattern = qr/$filePattern/;

        # read directory
        opendir my $dh, $dir || next;
        while ( my $file = readdir($dh) ) {
            $file = $dir . '/' . $file;
            next unless $file =~ $filePattern;
            $files++;
            $filesParsed++
              if defined parseFile( $linesByDate, $file, $targetDate, $blackList, $name );
        }
        close $dh;
    }

    printf( "parsed %d of %d files\n", $filesParsed, $files );

    my @dates = sort { $a cmp $b } keys %$linesByDate;

    print join( "", ( map { join( "", @{ $linesByDate->{$_} } ) } @dates ) );
}

sub main {
    my $start  = time();
    my $cgi    = new CGI::Simple();
    my $params = $cgi->Vars;

    my $year  = '';
    my $month = '';
    my $day   = '';

    if ( $params->{date} eq 'today' ) {
        $params->{date} = epochToDatetime();
    }
    if ( $params->{date} =~ /(\d\d\d\d)\-(\d\d)\-(\d\d)/ ) {
        $year  = $1;
        $month = $2;
        $day   = $3;
    }

    #if ($ENV{HTTP_REFERER}=~/log/){
    print $cgi->header('text/html;charset=utf-8');
    printError( 'config file does not exist', 'exit' ) unless -e $webConfigFile;
    printError( 'cannot read config file',    'exit' ) unless -r $webConfigFile;

    my $config = Config::General->new($webConfigFile);
    $config = $config->{DefaultConfig};
    printError( 'no config set', 'exit' ) unless defined $config;
    $webappDir    = $config->{web}->{webAppDir};
    $outputStream = $config->{web}->{outputStream};

    printHeader();

    exit if ( $params->{date} eq '' );

    parseFiles( $year, $month, $day );

    my $content = '';
    $content .= '</pre>';
    $content .= sprintf( "took %.2f seconds\n", ( time() - $start ) );
    $content .= '</div></body></html>';

    print $content;

}

main();

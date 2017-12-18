#/usr/bin/perl
use CGI;
use Data::Dumper;

use strict;
use warnings;

our $webConfigFile = '/etc/stream-schedule/webapp/stream-schedule.conf';

binmode STDOUT, ":encoding(UTF-8)";

my $cgi    = new CGI();
my $params = $cgi->Vars;

my $debug = 0;
my $date  = '';
my $year  = '';
my $month = '';
my $day   = '';

our $webappDir    = '.';
our $outputStream = '';

if ( $params->{date} eq 'today' ) {
    $params->{date} = epochToDatetime();
}
if ( $params->{date} =~ /(\d\d\d\d)\-(\d\d)\-(\d\d)/ ) {
    $year  = $1;
    $month = $2;
    $day   = $3;
    $date  = $year . '-' . $month . '-' . $day;
}

#if ($ENV{HTTP_REFERER}=~/log/){
print $cgi->header('text/html;charset=utf-8');

use Config::General;
printError( 'config file does not exist', 'exit' ) unless ( -e $webConfigFile );
printError( 'cannot read config file',    'exit' ) unless ( -r $webConfigFile );

my $config = new Config::General($webConfigFile);
$config = $config->{DefaultConfig};
printError( 'no config set', 'exit' ) unless ( defined $config );
$webappDir    = $config->{web}->{webAppDir};
$outputStream = $config->{web}->{outputStream};

printHeader();
print q{
    <link type="text/css" href="css/jquery-ui.min.css" rel="stylesheet" />	
<script type="text/javascript" src="js/jquery-ui.min.js"></script>
<script type="text/javascript" src="js/log.js"></script>

<div class="panel">
<form id="form" action="log.cgi" method="get">
	<p>Date: <input name="date" type="text" class="datepicker" size="30"/></p>
</form>	
<pre>
};

exit if ( $params->{date} eq '' );

#}

my $settings = {
    liquidsoap => {
        name  => 'liquidsoap',
        files => '/var/log/stream-schedule/liquidsoap.log',
        blacklist =>
          [ 'localhost disconnected', 'New client: localhost', 'Client disconnected', 'Re-opening output file' ],
    },
    scheduler => {
        name  => 'scheduler',
        files => '/var/log/stream-schedule/scheduler.log',
    },
    icecast => {
        name  => 'icecast2',
        files => '/var/log/icecast2/error.log',
        blacklist => [
            "checking for file /radio1",
            "checking for file /radio2",
            '/web/radio1" No such file or directory',
            '/web/radio2" No such file or directory'
        ]
    },
};

my $results = [];
my $names   = [];

#rver:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] New client: localhost.

my $line_counter = 0;
my $file_counter = 0;
for my $process ( keys %$settings ) {
    my @files = glob( $settings->{$process}->{files} . '*' );
    for my $file (@files) {

        #only logrotate files
        next unless ( ( $file =~ /log(\.\d+)?(\.gz)?$/ ) );
        $file_counter++;

        my $cmd       = '';
        my $file_type = `file '$file'`;
        print $file. "\t" . $file_type . "\n" if ( $debug == 1 );
        if ( $file_type =~ /gzip compressed/ ) {
            $cmd = "zcat '" . $file . "'";
        }
        if ( $file_type =~ /text/ ) {
            $cmd = "cat '" . $file . "'";
        }
        next if ( $cmd eq '' );
        print "$file\n" if ( $debug == 1 );

        my @stat = stat($file);
        my $size = $stat[7];
        if ( ( $file_type =~ /ASCII/ ) && ( $size > 2000000 ) ) {
            print "$file is to big! ignore...\n";
            next;
        } elsif ( ( $file_type =~ /gzip compressed/ ) && ( $size > 500000 ) ) {
            print "$file is to big! ignore...\n";
            next;
        }

        #add blacklist parameters
        for my $blacklist ( @{ $settings->{$process}->{blacklist} } ) {
            $cmd .= q{ | grep -v '} . $blacklist . q{'};
        }

        $cmd .= ' | egrep "^\[?' . $year . '[\/\-]' . $month . '[\/\-]' . $day . '"' if ( $date ne '' );

        print $cmd. "\n" if ( $debug == 1 );
        my $log_content = `$cmd`;

        my @lines            = ();
        my $liquidsoap_start = 0;
        for my $line ( split /\n/, $log_content ) {
            $line_counter++;

            #2016/03/25 13:40:28
            $line =~ s/^(\d\d\d\d)\/(\d\d)\/(\d\d)/$1\-$2\-$3/;

            #[2016-03-25  13:40:28]
            $line =~ s/^\[([\d\-]+)\s+([\d\:]+)\]/$1 $2/;

            if ( $line =~ /^\d\d\d\d\-\d\d\-\d\d / ) {

                my $ignore_line = 0;

                if ( $line =~ /\[main\:\d\] Liquidsoap / ) {
                    $liquidsoap_start = 1;
                } elsif ( $line =~ /\[main\:\d\] Using / ) {
                    $liquidsoap_start = 1;
                } elsif ( $liquidsoap_start == 1 ) {
                    if ( $line =~ /\[main\:\d\]/ ) {
                        $ignore_line = 1;
                    } else {
                        $liquidsoap_start = 0;
                    }
                }

                #liquidsoap: aggregate Buffer overruns
                elsif (( $line =~ /Buffer overrun/ )
                    && ( $lines[-1] =~ /Buffer overrun/ )
                    && ( $lines[-2] =~ /Buffer overrun/ ) )
                {
                    pop @lines;
                    if ( $lines[-1] =~ /\[(\d+) times\]$/ ) {
                        my $val = $1 + 1;
                        $lines[-1] =~ s/\[(\d+) times\]$/\[$val times\]/;
                    } else {
                        $lines[-1] .= "\t[1 times]";
                    }
                }

                #liquidsoap: dummy lines
                elsif ( $line =~ /dummy/ ) {
                    $ignore_line = 1;
                }

                #icecast: aggregate 'seen initial'
                elsif (
                       ( $line =~ /seen initial/ )
                    && ( $lines[-1] =~ /seen initial/ )

                    #					&& ($lines[-2]=~/seen initial/)
                  )
                {

                    #					pop @lines;
                    if ( $lines[-1] =~ /\[(\d+) times\]$/ ) {
                        my $val = $1 + 1;
                        $lines[-1] =~ s/\[(\d+) times\]$/\[$val times\]/;
                    } else {
                        $lines[-1] .= "\t[1 times]";
                    }
                    $ignore_line = 1;
                }

                #2016-03-24 07:48:40 -9	current	'default' since	2016-03-23 06:30:00
                #2016-03-24 07:48:40 -8	PLAY	default
                #2016-03-24 07:48:40 -7 liquidsoap stationstation1 plays:	http://wbox-lottum.ath.cx:8765/radio
                #2016-03-24 07:48:40 -6 liquidsoap stationstation2 plays:	http://wbox-lottum1.ath.cx:8765/radio
                #2016-03-24 07:48:40 -5 next in	2 day 9 hours 11 min 12 secs	frrapo at 2016-03-26 18:00:00
                #2016-03-24 07:49:10 -4 current	'default' since	2016-03-23 06:30:00
                #2016-03-24 07:49:10 -3	PLAY	default
                #2016-03-24 07:49:10 -2	liquidsoap stationstation1 plays:	http://wbox-lottum.ath.cx:8765/radio
                #2016-03-24 07:49:10 -1	liquidsoap stationstation2 plays:	http://wbox-lottum1.ath.cx:8765/radio
                #2016-03-24 07:49:10 	next in	2 day 9 hours 10 min 42 secs	frrapo at 2016-03-26 18:00:00

                #scheduler aggregate current play
                elsif (    #scheduler
                    ( $line =~ /next in/ )
                    #					&& (@lines>10)
                    #					&& ( substr($lines[-1],19) eq substr($lines[-6],19) )
                    #					&& ( substr($lines[-2],19) eq substr($lines[-7],19) )
                    #					&& ( substr($lines[-3],19) eq substr($lines[-8],19) )
                    #					&& ( substr($lines[-4],19) eq substr($lines[-9],19) )
                  )
                {

                    #get previous "next in" line in the last 10 lines
                    my $delta = 4;
                    while ( ( $delta < 8 ) && ( !( $lines[ -$delta ] =~ /next in/ ) ) ) {
                        $delta++;
                    }
                    if ( ( @lines > $delta ) && ( $lines[ -$delta ] =~ /next in/ ) ) {
                        my $duplicate = 1;
                        for my $i ( 1 .. $delta - 1 ) {
                            if ( substr( $lines[ -$i ], 19 ) eq substr( $lines[ -$i - $delta ], 19 ) ) {
                                $duplicate++;
                            }
                        }

                        if ( $duplicate == $delta ) {
                            for my $i ( 1 .. $delta ) {
                                pop @lines;
                            }
                        }
                    }

                } elsif ( $line =~ /\[error_announcer\:\d\] Finished with/ ) {
                    if ( $lines[-5] =~ /\[error_announcer\:\d\] Finished with/ ) {
                        pop @lines;
                        pop @lines;
                        pop @lines;
                        pop @lines;
                        if ( $lines[-1] =~ /\[(\d+) times\]$/ ) {
                            my $val = $1 + 1;
                            $lines[-1] =~ s/\[(\d+) times\]$/\[$val times\]/;
                        } else {
                            $lines[-1] .= "\t[1 times]";
                        }

                        $ignore_line = 1;
                    }
                }

                #log this line unless marked as to be ignored
                if ( $ignore_line == 0 ) {
                    push @lines, $line;    # unless ($line eq $lines[-1]);
                }
            }
        }

        #collect results and its process names
        push @$results, \@lines;
        push @$names,   $settings->{$process}->{name};
    }
}

#print Dumper($results);
#exit;

#set number of lines and current line number for all result logs
my $max_rows = [];
my $line_nr  = [];
for my $result (@$results) {
    push @$max_rows, @$result + 0;
    push @$line_nr,  0;
}

my @log = ();
for my $i ( 0 .. 100000 ) {
    my $min_date   = '9999-99-99 99:99:99';
    my $min_row_nr = 0;
    my $min_value  = undef;
    my $found      = 0;

    for my $row_nr ( 0 .. @$results - 1 ) {
        if ( $line_nr->[$row_nr] < $max_rows->[$row_nr] ) {
            my $row_value = $results->[$row_nr]->[ $line_nr->[$row_nr] ];
            my $row_date = substr( $row_value, 0, 19 );

            if ( $row_date lt $min_date ) {
                $min_row_nr = $row_nr;
                $min_date   = $row_date;
                $min_value  = substr( $row_value, 20 );
                $min_value  = $row_date . "\t" . $names->[$row_nr] . "\t" . $min_value;

                $found = 1;
            }
        }
    }
    last unless ( $found == 1 );
    push @log, $min_value if ( defined $min_value );
    $line_nr->[$min_row_nr]++;

    #	print"$min_row_nr:\t$line_nr->[$min_row_nr]\t<\t$max_rows->[$min_row_nr]\t$min_value <-- selected\n";
}
print "found and merged " . ( @log + 0 ) . " significant lines";
print " out of " . $line_counter;
print " in " . $file_counter . " files\n\n";
my $content = join( "\n", @log );
print $content;

sub printHeader {
    my $header = loadFile( $webappDir . "/template/header.html" );
    $header =~ s/\$outputStream/$outputStream/g;
    print $header;
}

sub epochToDatetime {
    my $time = shift;

    $time = time() unless ( ( defined $time ) && ( $time ne '' ) );
    ( my $sec, my $min, my $hour, my $day, my $month, my $year ) = localtime($time);
    my $datetime = sprintf( "%4d-%02d-%02d %02d:%02d:%02d", $year + 1900, $month + 1, $day, $hour, $min, $sec );
    return $datetime;
}

sub loadFile {
    my $filename = $_[0];

    my $content = '';
    if ( -e $filename ) {
        open my $FILE, "<", $filename || printError("cant read file '$filename'!");
        my $content = join "", (<$FILE>);
        close $FILE;
        return $content;
    } else {
        printError("cant access file '$filename'!");
    }
    return '';
}

sub printError {
    my $message = shift;
    my $option  = shift;
    print qq{<div class="error"><span class="icon" >&nbsp; &nbsp; &nbsp;</span>$message</div>};
    exit if ( $option eq 'exit' );
}


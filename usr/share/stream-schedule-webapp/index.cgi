#/usr/bin/perl

use strict;
use warnings;

use CGI qw();
use Data::Compare qw();
use Date::Language qw();
use Config::General qw();
use POSIX qw(strftime);
use Storable qw();
use Data::Dumper;

our $webConfigFile      = '/etc/stream-schedule/webapp/stream-schedule.conf';
our $scheduleConfigFile = '/etc/stream-schedule/stream-schedule.conf';

binmode STDOUT, ":encoding(UTF-8)";

our $cgi = new CGI();
print $cgi->header('text/html;charset=utf-8');

our @localtime = localtime();
our $date      = strftime( "%Y-%m-%d", @localtime );
our $datetime  = localtime();

our $params = $cgi->Vars;
$params->{details}  = '' unless defined $params->{details};
$params->{debug}    = '' unless defined $params->{debug};
$params->{stations} = '' unless defined $params->{stations};
$params->{action}   = '' unless defined $params->{action};

printError( 'web config file does not exist',                         'exit' ) unless ( -e $webConfigFile );
printError( 'cannot read web config file. PLease check permissions.', 'exit' ) unless ( -r $webConfigFile );
our $webConfig = new Config::General($webConfigFile);
$webConfig = $webConfig->{DefaultConfig};
printError( 'no config set', 'exit' ) unless ( defined $webConfig );

printError( 'stream-schedule config file does not exist. Please install stream-schedule first.', 'exit' )
  unless ( -e $scheduleConfigFile );
printError( 'cannot read stream-schedule config file. Please check permissions', 'exit' )
  unless ( -r $scheduleConfigFile );
our $scheduleConfig = new Config::General($scheduleConfigFile);
$scheduleConfig = $scheduleConfig->{DefaultConfig};
printError( 'no schedule config set', 'exit' ) unless ( defined $scheduleConfig );

our $webappDir    = $webConfig->{web}->{webAppDir}    || '';
our $outputStream = $webConfig->{web}->{outputStream} || '';
our $language     = $webConfig->{web}->{language}     || '';

our $sec  = 0;
our $min  = 60;
our $hour = 60 * $min;
our $day  = 24 * $hour;

our $lang = Date::Language->new($language);

our $schedulerStatusFile = $scheduleConfig->{scheduler}->{statusFile};
our $scheduleFile        = $scheduleConfig->{scheduler}->{scheduleFile};
our $syncTriggerFile     = $scheduleConfig->{scheduler}->{triggerSyncFile};

printHeader();

my $imageUrl  = "/stream-schedule-plot/monitor-$date.svg";
my $imageFile = "/var/log/stream-schedule/plot/monitor-$date.svg";
print qq{<a href="$imageUrl" id="plot"><img src="$imageUrl" width="100%" ></a>} . "\n"
  if ( -e $imageFile ) && ( $params->{stations} eq '' );

checkSync($params);
my $status = getStatus();

#print STDERR Dumper($status);
if ( $params->{stations} ne '' ) {
	printStations( $params, $status->{stations} );
} else {
	printStatus( $params, $status );
}
printFooter();

sub checkSync {
	my $params = shift;
	if ( $params->{action} eq 'sync' ) {
		saveFile( 'scheduler/triggerSyncFile', $syncTriggerFile, '' );
		print qq{<meta http-equiv="refresh" content="15;url=index.cgi" />} . "\n";
	} else {
		print qq{<meta http-equiv="refresh" content="60;url=index.cgi" />} . "\n";
	}
}

sub getFileAge {
	my $file  = shift;
	my @stats = stat($file);
	return $stats[9];
}

sub getStatus {
	my $now = time();

	#get files age
	my $statusAge      = getFileAge($schedulerStatusFile);
	my $scheduleAge    = getFileAge($scheduleFile);
	my $syncTriggerAge = getFileAge($syncTriggerFile);

	#read schedule status
	my $status = Storable::retrieve($schedulerStatusFile);
	$status->{statusAge}      = $statusAge;
	$status->{scheduleAge}    = $scheduleAge;
	$status->{now}            = $now;
	$status->{syncTriggerAge} = $syncTriggerAge;

	#evaluate status

	my $warnings = $status->{warnings};

	my $isPlanEmpty = 0;
	$isPlanEmpty = 1 if defined getMessage( $warnings, "empty schedule" );
	removeMessage( $warnings, "no future entries" ) if $isPlanEmpty == 1;

	for my $key ( sort keys( %{$warnings} ) ) {
		printInfo($key);
	}

	my $isSchedulerRunning = 1;
	$isSchedulerRunning = 0 if $now - $statusAge > 1 * $min;
    $status->{isSchedulerRunning} = $isSchedulerRunning;

	if ( $isSchedulerRunning != 0 ) {
	    my $isLiquidsoapRunning = 1;
	    if (   ( $status->{liquidsoap}->{cli} =~ /problem connecting to/ )
		    || ( $status->{liquidsoap}->{cli} =~ /liquidsoap is not available/ ) )
	    {
		    printError("liquidsoap is not running!");
		    removeMessage( $warnings, "liquidsoap is not available" );
		    removeMessage( $warnings, "invalid stream URL" );
		    $isLiquidsoapRunning = 0;
	    }
	    $status->{isLiquidsoapRunning} = $isLiquidsoapRunning;
    }

	if ( $isSchedulerRunning == 0 ) {
		printError("Scheduler is not running!");
	} else {
		printInfo('synchronization initiated. This can take up to one minute.')
		  if $syncTriggerAge > $statusAge;
		printInfo("schedule will be updated during next minute!")
		  if ( $scheduleAge - $statusAge > 0 ) && ( $scheduleAge - $statusAge <= 30 * $sec );
	}
	printInfo("schedule is older than 1 day!") if $now - $scheduleAge > 1 * $day;
	printInfo("schedule has been updated")     if $scheduleAge - $statusAge > 30 * $sec;

	my $output = qq{
        <div id="time" class="panel"><br>
            <table>
    };
	$output .= '<tr><td>now</td><td class="date">' . formatDateSec($now) . '</td></tr>' . "\n";
	$output .= '<tr><td>status</td><td class="date">' . formatDateSec($statusAge) . '</td></tr>' . "\n";
	$output .= '<tr><td>schedule age</td><td class="date">' . formatDateSec($scheduleAge) . '</td></tr>' . "\n";
	$output .= qq{
            </table>
        </div>
    };
    print $output;
	return $status;
}

sub getMessage {
	my $messages = shift;
	my $pattern  = shift;

	for my $message ( keys %$messages ) {
		return $message if $message =~ /$pattern/;
	}
	return undef;
}

sub removeMessage {
	my $messages = shift;
	my $pattern  = shift;

	for my $message ( keys %$messages ) {
		delete $messages->{$message} if $message =~ /$pattern/;
	}
}

sub printStatus {
	my $params = shift;
	my $status = shift;

    if ($status->{isLiquidsoapRunning}){
    	printLiquidsoapStatus($status);
	}
	printScheduleStatus() if $params->{details} ne '';
	printSchedule($status);

	if ( $params->{details} ne '' ) {
		my $output = qq{<table><tr><td>};
		printStation( $status->{current}, 'current' );
		$output .= qq{</td><td>};
		printStation( $status->{next}, 'next' );
		$output .= qq{</td></tr></table>};
		print $output;
	}
}

sub printLiquidsoapStatus {
	my $status = shift;

	my $output = qq{
        <div class="panel">
        <h3>liquidsoap - now playing</h3>
    };

	my $url1 = $status->{liquidsoap}->{station1}->{url} || '';

	my $url = $url1;
	if ( $url =~ /(https?\:\/\/)/ ) {
		my $protocol = $1;
		my @status = split( /https?\:\/\//, $url );
		$url = $protocol . $status[-1];
	}
	$url1=~s!connected!<span style="background:green">connected</span>!;
	$url1=~s!stopped!<span style="background:red">stopped</span>!;
	$url1=~s!polling!<span style="background:yellow">polling</span>!;
	$output .= qq{URL1: <a href="$url">$url1</a><br/>} . "\n";

	my $url2 = $status->{liquidsoap}->{station2}->{url} || '';

	$url = $url2;
	if ( $url =~ /(https?\:\/\/)/ ) {
		my $protocol = $1;
		my @status = split( /https?\:\/\//, $url );
		$url = $protocol . $status[-1];
	}
	$url2=~s!connected!<span style="background:green">connected</span>!;
	$url2=~s!stopped!<span style="background:red">stopped</span>!;
	$url2=~s!polling!<span style="background:yellow">polling</span>!;
	$output .= qq{URL2: <a href="$url">$url2</a><br/>} . "\n";

	if ( $url1 =~ /invalid_url/ ) {
		printInfo('station1 : invalid URL!');
	} elsif ( $status->{liquidsoap}->{station1}->{error} ne '' ) {
		printInfo( 'URL1: ' . $status->{liquidsoap}->{station1}->{error} );
	} elsif ( $status->{liquidsoap}->{station2}->{error} ne '' ) {
		printInfo( 'URL2: ' . $status->{liquidsoap}->{station2}->{error} );
	}

	if ( $params->{details} ne '' && ( $status->{liquidsoap}->{cli} ne '' ) ) {
		$output .= '<div class="panel schedule">' . $status->{liquidsoap}->{cli} . '</div>' . "\n";
	}

	$output .= qq{</div>} . "\n";
	print $output;

}

sub printStations {
	my $params   = shift;
	my $stations = shift;

	my $output = qq{
        <div class="panel" style="clear:both;">
            <h3>stations</h3>
            To schedule one of the stations below, put one of the comma-separated aliases into the Google calendar event title
        </div>
        <div class="panel">
            <div><table><thead><tr>
    };
	for my $key ( 'title', 'alias', 'URL / fallback URL' ) {
		$output .= qq{<th class="$key">$key</th>} . "\n";
	}
	$output .= qq{</tr></thead>}."\n";

	for my $name ( keys %$stations ) {
		delete $stations->{$name} unless defined $stations->{$name};
	}

	for my $name ( sort { $stations->{$a}->{title} cmp $stations->{$b}->{title} } ( keys %$stations ) ) {
		my $station = $stations->{$name};

		# ignore aliases
		next unless $station->{id} eq $name;
		next unless ( defined $station->{alias} ) && ( $station->{alias} ne '' );
		$output .= qq{<tr>};
		for my $key ( 'title', 'alias' ) {
			my $value=$station->{$key};
			$output .= qq{<td class="$key">$value</td>} . "\n";
		}
		my $url1 = $station->{url1};
		my $url2 = $station->{url2};
		( my $status1, my $status2 ) = checkUrls( $url1, $url2 );
		$output .= qq{<td><a href="$url1" class="$status1">$url1</a>};
		$output .= qq{<br><a href="$url2" class="$status2">$url2</a><br>} if $url2 ne '';
		$output .= qq{</td>};
		$output .= qq{</tr>};

	}
	$output .= qq{
        </tbody></table></div>
        </div>
    };
	print $output;
}

sub printSchedule {
	my $status = shift;

	my $schedule = $status->{schedule};
	my $current  = $status->{current};

	my $output = qq{
        <div class="panel schedule" style="clear:both;">
        <h3>schedule</h3>
        <table><thead><tr>
    };
	for my $key ( 'date', 'start', 'station', 'title', 'URLs' ) {
		$output .= qq{<th class="$key">$key</th>} . "\n";
	}
	$output .= qq{
        </tr></thead>
        <tbody>
    };
	for my $event (@$schedule) {
		my $class = '';
		if ( ( $event->{date} cmp $current->{date} ) < 1 ) {
			$class = ' class="old"';
		}
		if ( Data::Compare::Compare( $event, $current ) == 1 ) {
			$class = ' class="current"';
		}
		$output .= qq{<tr$class>} . "\n";

		my $date = formatDate( datetimeToEpoch( $event->{date} ) );

		$output .= qq{<td class="date">$date</td>} . "\n";

		my $duration = $event->{epoch} - $status->{statusAge};
		$output .= qq{<td>} . formatDuration($duration) . qq{</td>};

		$output .= qq{<td>$event->{station}->{title}</td>} . "\n";

		$output .= qq{<td>$event->{name}</td>} . "\n";

		my $url1 = $event->{station}->{url1};
		my $url2 = $event->{station}->{url2};
		( my $status1, my $status2 ) = checkUrls( $url1, $url2 );
		$output .= qq{<td><a href="$url1" class="$status1">$url1</a>} . "\n";
		$output .= qq{<br><a href="$url2" class="$status2">$url2</a><br>} . "\n" if ( $url2 ne '' );
		$output .= qq{</td></tr>} . "\n";
	}
	$output .= qq{
        </tbody></table>
        </div>
    };
	print $output;

}

sub printStation {
	my $entry = shift;
	my $title = shift;

	my $station = $entry->{station};

	my $output = qq{
        <div class="panel">
        <h3>$title</h3>
        <table>
            <tbody>
            <tr>
                <td>date</td>
                <td>$entry->{date}</td>
            </tr>
    };

	for my $key ('title id') {
		$output .= qq{
            <tr>
                <td>$key</td>
                <td>$station->{$key}</td>
            </tr>
        };
	}
	my $url1 = $station->{url1};
	my $url2 = $station->{url2};
	( my $status1, my $status2 ) = checkUrls( $url1, $url2 );

	$output .= qq{
            <tr>
                <td>url1</td>
                <td><a href="$url1" class="$status1">$url1</a></td>
            </tr>
            <tr>
                <td>url2</td>
                <td><a href="$url2" class="$status2">$url2</a></td>
            </tr>
    };
	$output .= qq{
            </tbody>
        </table>
        </div>
    };
	print $output;
}

sub printScheduleStatus {

	my $output = '<div class="panel scheduleStatus">';
	$output .= "<h3>schedule content</h3>\n";
	my $content = loadFile($scheduleFile);
	$output .= '<pre>' . $content . '</pre>';
	$output .= '</div>';
	print $output;
}

#helpers following

sub printHeader {
	my $header = loadFile( $webappDir . "/template/header.html" );
	$header =~ s/\$outputStream/$outputStream/g;
	print $header. "\n";
}

sub printFooter {
	print qq{
    </body></html>
    };
}

sub printError {
	my $message = shift;
	my $option = shift || '';
	print qq{<div class="error"><span class="icon" >&nbsp; &nbsp; &nbsp;</span>$message</div>} . "\n";
	print STDERR "[$datetime] [error] " . $message . "\n";
	exit if ( $option eq 'exit' );
}

sub printInfo {
	print qq{<div class="info"><span class="icon" />&nbsp; &nbsp; &nbsp;</span>$_[0]</div>} . "\n";
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

sub saveFile {
	my $label    = $_[0];
	my $filename = $_[1];
	my $content  = $_[2];
	if ( $filename =~ /[^a-z0-9\.\-\_\/]/ ) {
		printError("invalid filename for $label");
	}

	#check if directory is writeable
	if ( $filename =~ /^(.+?)\/[^\/]+$/ ) {
		my $dir = $1;
		unless ( -w $dir ) {
			printError("cannot write to directory ($dir)");
			return;
		}
	}

	open my $FILE, ">", $filename || printError("cant open file '$filename' for writing!");
	if ( defined $FILE ) {
		print $FILE $content;
		close $FILE;
	}
	`chmod 665 $filename`;
}

sub checkUrls {
	my $url1 = shift;
	my $url2 = shift;

	my $status1 = 'ok';
	$status1 = 'error'    unless ( $url1 =~ /https?\:\/\// );
	$url1    = 'missing!' unless ( $url1 =~ /\S/ );

	my $status2 = 'ok';
	$status2 = 'error' unless ( $url2 =~ /https?\:\/\// );
	return ( $status1, $status2 );
}

sub formatDuration {
	my $date     = shift;
	my $duration = $date;
	my $s        = 'in ';
	if ( $duration < 0 ) {
		$duration *= -1;
		$s = '';
	}
	my $time = $duration;
	if ( $time > $day ) {
		my $days = int( $time / $day );
		$time -= $days * $day;
		$s .= $days . ' day';
		$s .= 's' if ( $days > 1 );
		$s .= ' ';
	}
	if ( $time > $hour ) {
		my $hours = int( $time / $hour );
		$time -= $hours * $hour;
		$s .= $hours . ' hour';
		$s .= 's' if ( $hours > 1 );
		$s .= ' ';
	}
	if ( $duration < 6 * $hour ) {
		if ( $time > $min ) {
			my $mins = int( $time / $min );
			$time -= $mins * $min;
			$s .= $mins . ' min ';
		}
	}
	if ( $duration < 5 * $min ) {
		$s .= $time . " secs";
	}
	if ( $date < 0 ) {
		$s .= ' ago';
	}
	$s .= "\t" if ( length($s) < 5 );
	return $s;
}

sub datetimeToEpoch {
	my $datetime = shift;
	if ( $datetime =~ /(\d\d\d\d)\-(\d+)\-(\d+)[T\s](\d+)\:(\d+)(\:(\d+))?/ ) {
		my $year   = $1;
		my $month  = $2 - 1;
		my $day    = $3;
		my $hour   = $4;
		my $minute = $5;
		my $second = $7 || '00';
		return Time::Local::timelocal( $second, $minute, $hour, $day, $month, $year );

	} else {
		printError("datetimeToEpoch: no valid date time found! ($datetime)");
		return -1;
	}
}

sub formatDate {
	my $epoch = shift;
	return $lang->time2str( "%a %e.%b %R", $epoch );
}

sub formatDateSec {
	my $epoch = shift;
	return $lang->time2str( "%a %e.%b %T", $epoch );
}


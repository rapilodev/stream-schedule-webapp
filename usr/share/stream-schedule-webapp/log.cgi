#/usr/bin/perl
use strict;
use warnings;

use CGI;
use Data::Dumper;
use Time::HiRes qw(time);
use IO::Zlib;
use Time::Local;

our $webConfigFile = '/etc/stream-schedule/webapp/stream-schedule.conf';
our $webappDir     = '.';
our $outputStream  = '';

my $MB    = 1024 * 1024;
my $debug = 0;

my $settings = {
	liquidsoap => {
		name  => 'liquidsoap',
		files => '/var/log/stream-schedule/liquidsoap.log',
		blacklist =>
		  [ 'localhost disconnected', 'New client: localhost', 'Client disconnected', 'Re-opening output file', 'try again in ' ],
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
	exit if $option eq 'exit';
}

sub getFileProperties {
	my $file = shift;
	my @stat = stat($file);
	my $size = $stat[7];
	my $modifiedAt = $stat[9];
	return {
	    size       => $size, 
	    modifiedAt => $modifiedAt
	};
}


#1524953936
#1527458400 

sub parseFile {
	my $linesByDate = shift;
	my $file        = shift;
	my $targetDate  = shift;
	my $blackList   = shift;
	my $name        = shift;

    my ($year, $month, $day) = split /\-/, $targetDate;
    my $targetEpoch= timelocal(0,0,0,$day,$month-1,$year-1900);#+ 24 * 60 *60;    

	my $properties = getFileProperties($file);
	if ($properties->{modifiedAt} < $targetEpoch){
	    print "file $file is too old, modifiedAt=$properties->{modifiedAt}, targetEpoch=$targetEpoch \n";
	    return undef;
	}	

	my $fileType = `file '$file' 2>&1`;
	print $file. "\t" . $fileType . "\n" if $debug == 1;

	if ( ( $fileType =~ /ASCII/ ) && ( $properties->{size} > 5 * $MB ) ) {
		print "$file is to big! ignore...\n";
		return undef;
	} elsif ( ( $fileType =~ /gzip compressed/ ) && ( $properties->{size} > 1 * $MB ) ) {
		print "$file is to big! ignore...\n";
		return undef;
	}

	my $cmd = undef;
	if ( $fileType =~ /gzip compressed/ ) {
    	$cmd = new IO::Zlib;
    	$cmd->open($file, "rb");
		#open $cmd, "zcat '" . $file . "'|";
	} elsif ( $fileType =~ /text/ ) {
		open $cmd, '<', $file;
	} else {
	    print "file $file: could not open to read\n";
		return undef;
	}

	my $dateMatch = qr/([\[]?(\d\d\d\d)[\s\-\/]+(\d\d)[\s\-\/]+(\d\d)[\sT]+(\d\d)\:(\d\d)\:(\d\d)[\]]?\s+)/;
	my $duplicate = 1;
	my $line      = '';
    my $previousLine = '';
	my $datetime  = '';

	my $blackMatch = '(' . join( "|", @$blackList ) . ')';
	$blackMatch = qr/$blackMatch/;

    my $matchCounter=0;
    my $lineCounter=0;
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
				#print "file $file, date $date before target $targetDate, ignore\n";
			    next;
			}elsif ($date gt $targetDate){
				#print "file $file, date $date beyond target $targetDate, skip\n";
            	printf ("file %s: found %d of %d lines\n", $file, $matchCounter, $lineCounter);
				return 1;
			}
			$datetime = $date . " " . $hour . ":" . $min . ":" . $sec;
			#print "file $file line date='$datetime', match='$match'\n";
			$line = substr( $line, length($match) );
		}

		#add blacklist parameters
		next if $line =~ /$blackMatch/;

		$linesByDate->{$datetime} = [] unless defined $linesByDate->{$datetime};
		my $lines = $linesByDate->{$datetime};

        #$line=~s/\.\d+s//g;
        #$previousLine=~s/\.\d+s//g;
        #print "a:$line\nb:$previousLine\n";
		if ( $line eq $previousLine ) {
			#print "duplicate\n";
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
	printf ("file %s: found %d of %d lines\n", $file, $matchCounter, $lineCounter);
	#print "close file\n";
	return 1;
}

#rver:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] New client: localhost.

sub parseFiles {
	my $year  = shift;
	my $month = shift;
	my $day   = shift;

	my $targetDate = $year . '-' . $month . '-' . $day;

	my $results = [];
	my $names   = [];

	my $fileCounter = 0;
    my $filesParsed = 0;
	my $linesByDate = {};

	for my $process ( keys %$settings ) {
		my $name      = $settings->{$process}->{name};
		my $blackList = $settings->{$process}->{blacklist};

		my @files = glob( $settings->{$process}->{files} . '*' );
		for my $file (@files) {
			next unless $file =~ /log(\.\d+)?(\.gz)?$/;
			#print "parse $file\n";

			$fileCounter++;
			$filesParsed++ if defined parseFile( $linesByDate, $file, $targetDate, $blackList, $name );

			#collect results and its process names
		}
	}

	printf( "parsed %d of %d files\n", $filesParsed, $fileCounter );

	my @dates = sort { $a cmp $b } keys %$linesByDate;

	print join( "", ( map { join( "", @{ $linesByDate->{$_} } ) } @dates));
}

sub main {
	my $start  = time();
	my $cgi    = new CGI();
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

	use Config::General;
	printError( 'config file does not exist', 'exit' ) unless ( -e $webConfigFile );
	printError( 'cannot read config file',    'exit' ) unless ( -r $webConfigFile );

	my $config = new Config::General($webConfigFile);
	$config = $config->{DefaultConfig};
	printError( 'no config set', 'exit' ) unless ( defined $config );
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


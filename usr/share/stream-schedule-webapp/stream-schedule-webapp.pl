#!/usr/bin/env perl
use Mojolicious::Lite;
use Config::General();
use Const::Fast qw(const);
use File::Basename();
use File::ReadBackwards();
use Time::HiRes qw(time);
use Time::Local();
use PerlIO::gzip();
use POSIX qw(strftime);
use CGI::Carp qw(fatalsToBrowser);
use lib "lib";
use lib "$ENV{PERL5LIB}";
use StreamSchedule;

get '/' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $html = header() . join'',(
    qq{<div id="messages"></div>},
    q{<div id="content">},
        qq{<div class="panel" id="date-status"></div>},
        qq{<div class="panel" id="liquidsoap-status"></div>},
        qq{<div class="panel" id="schedule-ongoing"></div>},
        qq{<div class="panel" id="schedule-upcoming"></div>},
        qq{<div class="panel" id="audio-levels" class="panel"></div>},
        qq{<div class="panel" id="plot"></div>},
        qq{<div class="panel" id="schedule"></div>},
    qq{</div></body></html>}
    );
    $c->render(inline => $html, format => 'html');
};

get '/level' => sub {
    my $c = shift;
    StreamSchedule::init();
    my ($sec, $min, $hour, $day, $month, $year) = localtime(time);
    my $today = sprintf("%04d-%02d-%02d", $year + 1900, $month + 1, $day);
    
    my $path      = "/var/log/stream-schedule/plot/monitor-$today.log";
    my $backwards = File::ReadBackwards->new($path)
      or return $c->render(json => {msg => "cannot read data file"});
    chomp (my $line = $backwards->readline);
    my (
        $datetime,   $rmsLeftIn,   $rmsRightIn,  $peakLeftIn, $peakRightIn,
        $rmsLeftOut, $rmsRightOut, $peakLeftOut, $peakRightOut
    ) = split(/\t/, $line);

    $c->render(json => {
        datetime => $datetime,
        in       => {
            rmsLeft   => $rmsLeftIn,
            rmsRight  => $rmsRightIn,
            peakLeft  => $peakLeftIn,
            peakRight => $peakRightIn
        },
        out => {
            rmsLeft   => $rmsLeftOut,
            rmsRight  => $rmsRightOut,
            peakLeft  => $peakLeftOut,
            peakRight => $peakRightOut
        }
    });
};

get '/schedule' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status   = getStatus();
    my $schedule = $status->{schedule};
    my $current  = $status->{current};
    
    $c->render(inline=> div(
    {class => "schedule", style => "width:100%"},
    title("Schedule"),
    table(
        {class => "strict"},
        row(
            th('date'),    th('start'),
            th('station'), th('title'),
            th({class => "grow"}, 'URLs')
        ),
        map {
            my $event = $_;
            my $url1  = $event->{station}->{url1};
            my $url2  = $event->{station}->{url2};
            (my $status1, my $status2) = checkUrls($url1, $url2);
            my $class = '';
            $class = q{old}
              if ($event->{date} cmp $current->{date}) < 1;
            $class = q{current}
              if Data::Compare::Compare($event, $current) == 1;
            my $date = formatDate(datetimeToEpoch($event->{date}));
            my $duration =
              formatDuration($event->{epoch} - $status->{statusAge});
            row(
                {class => $class},
                td($date),
                td($duration),
                td($event->{station}->{title}),
                td($event->{name}),
                td({class => "grow"}, formatUrl($url1), formatUrl($url2))
            ),
        } (@$schedule)
    ))
    );
};

get '/date-status' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status   = getStatus();

    $c->render(inline=> div(
        title("Date"),
        table(
            row(
                td({class => "label"},            "date"),
                td(formatDateSec($status->{now}), {class => "date"})
            ),
            row(
                td({class => "label"},                  "last status update"),
                td(formatDateSec($status->{statusAge}), {class => "date"})
            ),
            row(
                td({class => "label"},                    "last schedule update"),
                td(formatDateSec($status->{scheduleAge}), {class => "date"})
            ),
        )
    ));
};

get '/plot' => sub {
    my $c = shift;
    StreamSchedule::init();
    our $date = strftime("%Y-%m-%d", localtime);
    my $imageUrl  = "/stream-schedule-plot/monitor-$date.svg";
    my $imageFile = "/var/log/stream-schedule/plot/monitor-$date.svg";
    die "no image file" unless -e $imageFile;
    $c->render(inline=> div(
        title("Audio Levels"),
        a( { href => $imageUrl, id => "plot" },
            qq{<img src="$imageUrl" width="100%" title="target peak=-3dB, target loudness=-20dB RMS">}
        )
    ));
};

sub station_row {
    my ($status, $name, $key) = @_;
    my $entry = $status->{liquidsoap}->{$key} || {};
    my $url   = $entry->{url} // '';
    my $label = $url;

    $url = $1 . (split(/https?:\/\//, $url))[-1] if $url =~ /(https?:\/\/)/;
    (my $cstatus, $url) = split /\s/, $label, 2;
    $cstatus =~
      s!(connected)!<span class="pin" style="background:green">$1</span>!;
    $cstatus =~ s!(stopped)!<span class="pin" style="background:red">$1</span>!;
    $cstatus =~
      s!(polling)!<span class="pin" style="background:yellow">$1</span>!;

    if ($label =~ /invalid_url/) {
        printInfo("$key : invalid URL!");
    } elsif (my $err = $entry->{error}) {
        printInfo("$name: $err");
    }
    return row [td({class => "label"},$name), td($cstatus), td({class => "grow"}, formatUrl($url))];
}

get '/liquidsoap-status' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status   = getStatus();

    $c->render(inline=> div(
        title("Status"),
        table(
            station_row($status,'primary',  'station1'),
            station_row($status, 'fallback', 'station2')
        )
    ));
};

get '/schedule-upcoming' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status  = getStatus();
    my $entry   = $status->{next};
    my $title   = 'Upcoming';
    my $station = $entry->{station};
    my $url1    = $station->{url1};
    my $url2    = $station->{url2};
    (my $status1, my $status2) = checkUrls($url1, $url2);
    $c->render(inline=> div(
        title($title),
        table(
            row(
                td({class => "label"}, "Date"),
                td({class => "grow"},  $entry->{date})
            ),
            row(
                td({class => "label"}, "Name"),
                td({class => "grow"},  $station->{title})
            ),
            row(
                td({class => "label"},         "primary"),
                td({class => "$status1 grow"}, formatUrl($url1))
            ),
            row(td({class => "label"}, "fallback"),
                td({class => "$status2 grow"}, formatUrl($url2)))
        )
    ));
};
get '/schedule-ongoing' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status  = getStatus();
    my $entry   = $status->{current};
    my $title   = 'Ongoing';
    my $station = $entry->{station};
    my $url1    = $station->{url1};
    my $url2    = $station->{url2};
    (my $status1, my $status2) = checkUrls($url1, $url2);
    $c->render(inline=> div(
        title($title),
        table(
            row(
                td({class => "label"}, "Date"),
                td({class => "grow"},  $entry->{date})
            ),
            row(
                td({class => "label"}, "Name"),
                td({class => "grow"},  $station->{title})
            ),
            row(
                td({class => "label"},         "primary"),
                td({class => "$status1 grow"}, formatUrl($url1))
            ),
            row(td({class => "label"}, "fallback"),
                td({class => "$status2 grow"}, formatUrl($url2)))
        )
    ));
};

get '/stations' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status = getStatus();
    my $stations = $status->{stations};
    for my $name (keys %$stations) {
        delete $stations->{$name} unless defined $stations->{$name};
    }

    $c->render(inline => header() . div(
        title("Stations"),
        q{To schedule one of the stations below, put one of the comma-separated aliases into the Google calendar event title},
        table(
            {class => "panel strict margin"},
            row(
                th('Title'),
                th('Alias'),
                th({class=>"grow"}, 'primary URL / fallback URL')
            ),
            (map {
                my $station = $_;
                my $url1 = $station->{url1};
                my $url2 = $station->{url2};
                (my $status1, my $status2) = checkUrls($url1, $url2);
                row (
                        td({class=>"title"}, $station->{title}),
                        td({class=>"alias"}, $station->{alias}),
                        td({class=>"grow"},
                            formatUrl($url1, {class=>$status1}) .
                            ($url2 eq ''  ? '' : formatUrl($url2, {class=>$status2}))
                        )
                );
            } sort {$a->{title} cmp $b->{title}}
                grep {$_->{alias}}
                map {$stations->{$_}}
                grep {$stations->{$_}->{id} eq $_}
                keys %$stations
            )
        )
    ));
};

get '/stream-status' => sub{
    my $c = shift;
    StreamSchedule::init();
    my $status = getStatus();
    my $result = {
        infos    => $status->{messages}->{infos},
        errors   => $status->{messages}->{errors},
        warnings => $status->{messages}->{warnings}
    };
    
    for my $num (1 .. 2) {
        my $res = $status->{liquidsoap}->{"station$num"}->{url} || '';
        my $url = $res;
        if ($url =~ /(https?\:\/\/)/) {
            my $protocol = $1;
            my @status   = split(/https?\:\/\//, $url);
            $url = $protocol . $status[-1];
        }
        push @{$result->{channel}},
          {
            status => $res,
            url    => $url
          };
    }
    
    if ($result->{"channel"}[0]->{url} =~ /invalid_url/) {
        push @{$result->{errors}}, 'station1 : invalid URL!';
    } elsif ($status->{liquidsoap}->{station1}->{error} ne '') {
        push @{$result->{errors}},
          'primary: ' . $status->{liquidsoap}->{station1}->{error};
    } elsif ($status->{liquidsoap}->{station2}->{error} ne '') {
        push @{$result->{errors}},
          'fallback: ' . $status->{liquidsoap}->{station2}->{error};
    }
    $c->render(json => $result);
};

get '/restart' => sub{
    my $c = shift;
    StreamSchedule::init();
    saveFile('scheduler/triggerRestartFile', $StreamSchedule::restartTriggerFile, '');
    $c->render(inline => "Restart Initiated");
};

get '/sync' => sub{
    my $c = shift;
    StreamSchedule::init();
    saveFile('scheduler/triggerSyncFile', $StreamSchedule::syncTriggerFile, '');
    $c->render(inline => "synchronization Initiated");
};

get '/stations' => sub {
    my $c = shift;
    StreamSchedule::init();
    my $status = getStatus();
    $c->render(inline => "synchronization Initiated");
};

our $settings = {
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


sub parseFile {
    my ($linesByDate, $file, $targetDate, $blackList, $name) = @_;
    const my $MB => 1024 * 1024;

    my ($year, $month, $day) = split /\-/, $targetDate;
    my $targetEpoch = Time::Local::timelocal(0, 0, 0, $day, $month - 1, $year - 1900)
      ;    #+ 24 * 60 *60;

    my @stats = stat $file;
    my $html='';
    my $modifiedAt = getModifiedAt(\@stats);
    if ($modifiedAt < $targetEpoch) {
        $html .= "file $file is too old, modifiedAt=$modifiedAt, targetEpoch=$targetEpoch \n";
        return undef;
    }

    my $fileType = getFileType($file);
    my $size     = getFileSize(\@stats);
    if (($fileType eq 'text') && ($size > 5 * $MB)) {
        $html .=  "$file is to big! ignore...\n";
        return undef;
    } elsif (($fileType eq 'gzip') && ($size > 1 * $MB)) {
        $html .=  "$file is to big! ignore...\n";
        return undef;
    }

    my $cmd = undef;
    if ($fileType eq 'gzip') {
        open $cmd, "<:gzip", $file or die $!;
    } elsif ($fileType =~ /text/) {
        open $cmd, '<', $file;
    } else {
        $html .=  "file $file ($fileType): could not open to read\n";
        return undef;
    }

    my $dateMatch = qr/([\[]?(\d\d\d\d)[\s\-\/]+(\d\d)[\s\-\/]+(\d\d)[\sT]+(\d\d)\:(\d\d)\:(\d\d)[\]]?\s+)/;
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
                $html .= sprintf("file %s: found %d of %d lines\n",
                    $file, $matchCounter, $lineCounter);
                return 1;
            }
            $datetime = $date . " " . $hour . ":" . $min . ":" . $sec;
            $line     = substr($line, length($match));
        }
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
    $html .= sprintf(
        "file %s: found %d of %d lines\n",
        $file, $matchCounter, $lineCounter);
    return $html;
}

#rver:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] Client localhost disconnected without saying goodbye..!
#2016-03-24 08:12:11 [server:3] New client: localhost.

sub parseFiles {
    my ($year, $month, $day) = @_;
    my $targetDate = "$year-$month-$day";
    my ($files, $filesParsed, %linesByDate);

    my $html =  q{<div class="panel" style="text-align:left;">};
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
            
            my $result = parseFile(\%linesByDate, $file, $targetDate, $blackList,
                $name);
            next unless $result;
            $filesParsed++;
            $html .= $result;
        }
        closedir $dh;
    }
    $html.= sprintf("<hr>parsed %d of %d files\n", $filesParsed, $files);
    $html.=  "</div>";

    $html.=  q{<div class="panel" style="text-align:left;">};
    $html.=  join "", map {join "", @{$linesByDate{$_}}} sort keys %linesByDate;
    $html.=  sprintf("<hr>took %.2f seconds\n", time() - $start);
    $html.=  "</div>";
    return $html;
}

get '/log' => sub{ 
    my $c = shift;
    StreamSchedule::init();
    my $status = getStatus();
    my $debug = 0;
    my $webConfigFile      = '/etc/stream-schedule/webapp/stream-schedule.conf';

    my $config = Config::General->new($webConfigFile);
    $config = $config->{DefaultConfig};
    die('no config set', 'exit') unless defined $config;
    my $webappDir    = $config->{web}->{webAppDir};
    my $outputStream = $config->{web}->{outputStream};

    my $header = loadFile($webappDir . "/template/header.html");
    $header =~ s/\$outputStream/$outputStream/g;
    my $html = $header . q{
        <script type="text/javascript" src="js/log.js"></script>
        <form id="form" action="log.cgi" method="get" style="position:absolute;left:1rem;top:0.5rem">
            Date <input name="date" type="date" class="datepicker" size="30" style="padding:1rem"/>
        </form>
        <div style="padding:1rem; white-space: pre-wrap;">};

    my $date = $c->param("date");
    $date = epochToDatetime() if $date eq 'today';
    exit if $date eq '';
    if ($date =~ /(\d\d\d\d)\-(\d\d)\-(\d\d)/) {
        $html .= parseFiles($1, $2, $3);
    }
    $c->render(inline => $html);
};

#get '/css/*file' => sub {
#  my $c = shift;
#  $c->reply->static($c->stash('file'));
#};
#
#get '/js/*file' => sub {
#  my $c = shift;
#  $c->reply->static($c->stash('file'));
#};

#push @{ app->static->paths }, app->home->rel_file('css');
#push @{ app->static->paths }, app->home->rel_file('js');
app->mode('production');
app->start($ENV{MOJO_MODE});
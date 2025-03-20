#!/usr/bin/perl
use strict;
use warnings;
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init;
my $status   = getStatus();
my $schedule = $status->{schedule};
my $current  = $status->{current};

print div(
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
    )
);

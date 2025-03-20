#!/usr/bin/perl
use strict;
use warnings;
use StreamSchedule;

binmode STDOUT, ":encoding(UTF-8)";
print "Content-type: text/html;charset=utf-8\n\n";

StreamSchedule::init();
printHeader();
my $status = getStatus();
my $stations = $status->{stations};
for my $name (keys %$stations) {
    delete $stations->{$name} unless defined $stations->{$name};
}

print div(
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
);

FROM ruby:3-alpine

ENV RUBYOPT "rubygems"
ENV BUNDLE_GEMFILE "/usr/src/CeWL/Gemfile"
ENV BUNDLE_PATH "/usr/src/CeWL/vendor/bundle"

COPY Gemfile Gemfile.lock /usr/src/CeWL/
WORKDIR /usr/src/CeWL

RUN set -ex \
    && apk add  --no-cache --virtual .build-deps build-base \
    && bundle install \
    && apk del .build-deps

COPY . /usr/src/CeWL

WORKDIR /host
ENTRYPOINT ["bundle", "exec", "/usr/src/CeWL/cewl.rb"]

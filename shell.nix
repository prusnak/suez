with import <nixpkgs> {};

let
  SuezPython = python3.withPackages(ps: [
    ps.black
    ps.click
    ps.rich
  ]);

in

stdenv.mkDerivation {
  name = "suez-env";
  buildInputs = [
    SuezPython
    poetry
  ];
}

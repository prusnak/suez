with import <nixpkgs> {};

let
  SuezPython = python3.withPackages(ps: [
    ps.rich
  ]);

in

stdenv.mkDerivation {
  name = "suez-env";
  buildInputs = [
    SuezPython
  ];
}

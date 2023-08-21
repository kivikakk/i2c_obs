{
  description = "Development shell for i2c_obs";

  inputs = {
    nixpkgs.follows = "hdx/nixpkgs";
    flake-compat = {
      url = github:edolstra/flake-compat;
      flake = false;
    };
    hdx.url = github:charlottia/hdx?ref=v0.1;
    hdx.inputs.amaranth.url = github:charlottia/amaranth?ref=wip;
  };

  outputs = inputs @ {
    self,
    nixpkgs,
    flake-utils,
    flake-compat,
    ...
  }: let
    overlays = [
      (final: prev: {
        hdx = inputs.hdx.packages.${prev.system};
      })
    ];
  in
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit overlays system;};
      hdx = pkgs.hdx.default;
      inherit (pkgs) lib;
      inherit (hdx) python;
    in rec {
      formatter = pkgs.alejandra;

      packages.default = python.pkgs.buildPythonPackage {
        name = "i2c_obs";

        format = "pyproject";
        src = ./.;

        nativeBuildInputs = builtins.attrValues {
          inherit
            (python.pkgs)
            setuptools
            black
            isort
            python-lsp-server
            ;

          inherit
            (pkgs.nodePackages)
            pyright
            ;

          inherit
            (pkgs)
            dfu-util
            ;

          inherit
            hdx
            ;
        };

        # dontAddExtraLibs = true;

        doCheck = true;

        pythonImportsCheck = ["i2c_obs"];

        checkPhase = ''
          BOARDS=( icebreaker orangecrab )
          SPEEDS=( 100000 400000 )
          export CI=1

          set -euo pipefail

          echo "--- Unit tests."
          python -m i2c_obs test

          for board in "''${BOARDS[@]}"; do
            for speed in "''${SPEEDS[@]}"; do
              echo "--- Building $board @ $speed."
              python -m i2c_obs build "$board" -s "$speed"
            done
          done

          echo "--- Formal verification."
          python -m i2c_obs formal

          echo "--- All passed."
        '';
      };

      checks.default = packages.default;

      devShells.default = packages.default;
    });
}

{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  buildInputs = with pkgs; [
    python313
    glib
    pango
    harfbuzz
    fontconfig
  ];

  shellHook = ''
    export LD_LIBRARY_PATH="${pkgs.glib.out}/lib:${pkgs.pango.out}/lib:${pkgs.harfbuzz}/lib:${pkgs.fontconfig.lib}/lib:$LD_LIBRARY_PATH"
    if [ -d venv ]; then
      source venv/bin/activate
    fi
  '';
}
